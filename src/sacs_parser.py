"""SACS unaudited-actuals .mdb -> General Fund spending by function group for one district.

Reads the Access database with the pure-Python `access-parser` package (no mdbtools needed).
Two quirks of access-parser on this file, verified for 2022-23, 2023-24 and 2024-25:
  1. Fixed-width Text columns come back as the field *plus every later field in the row*,
     so each one is cut to its documented width (sacs{yy}readme.docx).
  2. Decimal(18,2) columns come back as 17 raw bytes (see decode_decimal).
The decoder reproduces CDE's own state total in UserGL_Totals to the cent (state_total_check).

Parsing UserGL takes ~70s and ~4GB RAM, so each district's rows are cached as CSV.
"""
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import pandas as pd
from access_parser import AccessParser

from cds_lookup import CDS, RAW

CACHE = RAW / "cache"

# Text widths per fiscal year, copied from each year's bundled readme (sacs{yy}readme.docx).
# Only years whose readme has been read are listed; any other year raises, so a schema
# change can't slip through silently. Difference found so far: LEAs.Dname grew from 75
# (2022-23, 2023-24) to 100 (2024-25).
_UserGL = {"Ccode": 2, "Dcode": 5, "SchoolCode": 7, "Fiscalyear": 4, "Period": 4,
           "Colcode": 4, "Account": 19}
TEXT_WIDTHS = {
    "2223": {**_UserGL, "Dname": 75, "Dtype": 50},
    "2324": {**_UserGL, "Dname": 75, "Dtype": 50},
    "2425": {**_UserGL, "Dname": 100, "Dtype": 50},
}
EXPECTED_TABLES = {"UserGL", "UserGL_Totals", "LEAs", "Fund", "Resource", "Goal",
                   "Function", "Object", "Charters"}

# Spending scope (a documented project choice, not a CDE definition):
#   Fund 01 (General Fund), objects 1000-5999 (salaries, benefits, books/supplies,
#   services/operating) plus 7300-7399 (indirect-cost transfers, which net to zero within
#   the fund but move admin costs between functions).
#   Excluded: 6000s capital outlay, 7100-7299 transfers to other agencies,
#   7400-7499 debt service, 7600+ other financing uses.
FUND = "01"
OBJECT_RANGES = [("1000", "5999"), ("7300", "7399")]

# SACS major function groups (first digit of the function code).
FUNCTION_GROUPS = {
    "1": "1000 Instruction",
    "2": "2000 Instruction-Related Services",
    "3": "3000 Pupil Services",
    "4": "4000 Ancillary Services",
    "5": "5000 Community Services",
    "6": "6000 Enterprise",
    "7": "7000 General Administration",
    "8": "8000 Plant Services",
    "9": "9000 Other Outgo",
}


def decode_decimal(raw: bytes, scale: int = 2) -> Decimal:
    """Jet4 Decimal: byte 0 = sign (0x80 negative), then four little-endian uint32 words,
    most significant word first."""
    n = 0
    for i in range(1, 17, 4):
        n = (n << 32) | int.from_bytes(raw[i:i + 4], "little")
    return Decimal(-n if raw[0] & 0x80 else n).scaleb(-scale)


class SchemaError(Exception):
    pass


def widths(fiscal: str) -> dict[str, int]:
    if fiscal not in TEXT_WIDTHS:
        raise SchemaError(f"No verified field widths for SACS {fiscal}; read sacs{fiscal}readme.docx "
                          "and add them to TEXT_WIDTHS")
    return TEXT_WIDTHS[fiscal]


def _mdb(fiscal: str) -> AccessParser:
    widths(fiscal)
    db = AccessParser(str(RAW / f"sacs{fiscal}.mdb"))
    missing = EXPECTED_TABLES - set(db.catalog)
    if missing:
        raise SchemaError(f"SACS {fiscal} is missing tables {sorted(missing)}")
    return db


@lru_cache(maxsize=None)
def _small_table(fiscal: str, name: str) -> dict:
    """LEAs / Charters / code tables are small; parse each once per year."""
    return _mdb(fiscal).parse_table(name)


def fund01_charter_ada(cds: CDS, fiscal: str = "2425") -> float:
    """K-12 ADA of charter schools whose finances are reported inside this district's
    General Fund (Charters.FundUsed == 'General'). Their spending is in Fund 01 without a
    charter school code, but per the SACS readme their ADA is NOT in LEAs.K12ADA, so it
    must be added back to get a per-ADA figure that covers the same students as the spend.
    Matches Form A line C4 (Annual ADA); for LAUSD 2024-25 that's 34,895.44."""
    t = _small_table(fiscal, "Charters")
    return sum(float(t["K12ADA"][i]) for i in range(len(t["Ccode"]))
               if t["Ccode"][i][:2] == cds.county and t["Dcode"][i][:5] == cds.district
               and t["FundUsed"][i][:30].strip() == "General")


def lea(cds: CDS, fiscal: str = "2425") -> dict:
    """District name, type and ADA. `ada` (district K-12 ADA plus Fund 01 charter ADA) is the
    denominator for General Fund per-pupil spending; it equals CDE's Current Expense ADA."""
    w = widths(fiscal)
    t = _small_table(fiscal, "LEAs")
    for i in range(len(t["Ccode"])):
        if t["Ccode"][i][:2] == cds.county and t["Dcode"][i][:5] == cds.district:
            district_ada = float(t["K12ADA"][i])
            charter_ada = fund01_charter_ada(cds, fiscal)
            return {
                "district_name": t["Dname"][i][:w["Dname"]].strip(),
                "district_type": t["Dtype"][i][:w["Dtype"]].strip(),
                "k12_ada": district_ada,
                "fund01_charter_ada": charter_ada,
                "ada": round(district_ada + charter_ada, 2),
            }
    raise LookupError(f"{cds.code} not in SACS LEAs table for {fiscal}")


def state_total_check(fiscal: str) -> tuple[Decimal, Decimal]:
    """Sum of every district's Fund 01 objects 1000-7999 in UserGL vs the state row in
    UserGL_Totals. Equal to the cent means the decoder and width cuts are right for that
    year's file. Full-table parse: ~70s, ~4GB RAM."""
    db = _mdb(fiscal)
    in_range = lambda acct: acct[:2] == FUND and "1000" <= acct[15:19] <= "7999"
    gl = db.parse_table("UserGL")
    ours = sum((decode_decimal(v) for a, v in zip(gl["Account"], gl["Value"]) if in_range(a[:19])), Decimal(0))
    del gl
    tot = db.parse_table("UserGL_Totals")
    state = sum((decode_decimal(v) for c, d, a, v in zip(tot["Ccode"], tot["Dcode"], tot["Account"], tot["Value"])
                 if c[:2] == "99" and d[:5] == "99999" and in_range(a[:19])), Decimal(0))
    return ours, state


def code_titles(table: str, fiscal: str = "2425") -> dict[str, str]:
    """Code -> title from a lookup table (Fund, Resource, Goal, Function, Object)."""
    t = _small_table(fiscal, table)
    return {c[:4].strip(): ttl[:250].strip() for c, ttl in zip(t["Code"], t["Title"])}


def general_ledger(cds: CDS, fiscal: str = "2425") -> pd.DataFrame:
    """All UserGL rows for one district, with the account string split into segments."""
    cache = CACHE / f"usergl_{fiscal}_{cds.county}{cds.district}.csv"
    if cache.exists():
        df = pd.read_csv(cache, dtype=str)
        df["Value"] = df["Value"].map(Decimal)
        return df

    t = _mdb(fiscal).parse_table("UserGL")
    idx = [i for i, (c, d) in enumerate(zip(t["Ccode"], t["Dcode"]))
           if c[:2] == cds.county and d[:5] == cds.district]
    if not idx:
        raise LookupError(f"{cds.code} has no UserGL rows for {fiscal}")
    df = _ledger_frame(t, idx, fiscal)

    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache, index=False)
    return df


def _ledger_frame(t: dict, idx: list[int], fiscal: str) -> pd.DataFrame:
    """UserGL rows `idx` as a DataFrame: widths cut per year, Decimal values, account split."""
    df = pd.DataFrame({
        col: [t[col][i][:w] for i in idx]
        for col, w in widths(fiscal).items() if col in t
    })
    df["Value"] = [decode_decimal(t["Value"][i]) for i in idx]
    acct = df["Account"]
    df["Fund"], df["Resource"], df["Projectyear"] = acct.str[:2], acct.str[2:6], acct.str[6]
    df["Goal"], df["Function"], df["Object"] = acct.str[7:11], acct.str[11:15], acct.str[15:19]
    return df


def extract_county(fiscal: str, county: str = "19") -> list[str]:
    """Parse UserGL once and write the per-district cache that general_ledger() reads, for
    every district in one county (~70s and ~4GB per year, instead of that per district).
    Returns the 7-digit county+district codes written."""
    t = _mdb(fiscal).parse_table("UserGL")
    groups: dict[str, list[int]] = {}
    for i, (c, d) in enumerate(zip(t["Ccode"], t["Dcode"])):
        if c[:2] == county:
            groups.setdefault(c[:2] + d[:5], []).append(i)
    CACHE.mkdir(parents=True, exist_ok=True)
    for cd, idx in groups.items():
        _ledger_frame(t, idx, fiscal).to_csv(CACHE / f"usergl_{fiscal}_{cd}.csv", index=False)
    return sorted(groups)


def in_scope(gl: pd.DataFrame) -> pd.Series:
    obj = gl["Object"]
    in_range = pd.Series(False, index=gl.index)
    for lo, hi in OBJECT_RANGES:
        in_range |= obj.between(lo, hi)
    return (gl["Fund"] == FUND) & in_range


def spending_by_function(cds: CDS, fiscal: str = "2425") -> pd.DataFrame:
    """In-scope General Fund spending, summed by major function group."""
    gl = general_ledger(cds, fiscal)
    sel = gl[in_scope(gl)].copy()
    sel["function"] = sel["Function"].str[0].map(FUNCTION_GROUPS)
    out = sel.groupby("function", as_index=False)["Value"].sum()
    return out.rename(columns={"Value": "spend"})


def form01_function_totals(cds: CDS, fiscal: str = "2425") -> pd.Series:
    """General Fund expenditures by function group on the same basis as the district's
    Form 01 "Expenditures by Function" page: objects 1000-7499 (7600-7699 transfers out are
    reported separately as other financing uses). Includes capital outlay and other outgo,
    so it is broader than in_scope(). Used to check the ledger against the filing."""
    gl = general_ledger(cds, fiscal)
    sel = gl[(gl["Fund"] == FUND) & gl["Object"].between("1000", "7499")]
    by_fn = sel.groupby(sel["Function"].str[0].map(FUNCTION_GROUPS))["Value"].sum()
    by_fn["TOTAL"] = sel["Value"].sum()
    return by_fn


if __name__ == "__main__":
    import sys

    cds = CDS.parse(sys.argv[1] if len(sys.argv) > 1 else "19647330000000")
    print(lea(cds))
    print(spending_by_function(cds).to_string(index=False))
