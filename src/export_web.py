"""Export the data behind the static dashboard (docs/index.html).

    python src/export_web.py                       # all 79 LA County districts
    python src/export_web.py 19647330000000        # one district

Writes docs/data/<cds>.js per district (sets `window.MAIA_DATA[cds]`) and docs/data/index.js
(sets `window.MAIA_INDEX`, the district picker list). .js files (not .json) so the page works
both when opened straight from disk (file://, where fetch() is blocked) and on GitHub Pages.

Trend numbers come from the Phase 2 dataset (data/processed/la_county_2223-2425.csv); kinds of
dollars come from the verified SACS modules. Nothing in the pipeline is recomputed or changed.
"""
import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

import join
import sacs_parser
import sacs_statement
from cds_lookup import CDS

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "data"
COUNTY = ROOT / "data" / "processed" / "la_county_2223-2425.csv"

# Districts hand-verified against their own filings in Phase 2 (notes/phase2_signoff.md).
VERIFIED = {
    "19647330000000",  # Los Angeles Unified
    "19753410000000",  # Redondo Beach Unified
    "19646260000000",  # Hughes-Elizabeth Lakes Union Elementary
    "19651280000000",  # Whittier Union High
}

# The page shows 7 function series (the dataviz palette's adjacent-safe range); the three
# smallest groups fold into "Other". Order = stacking order = color slot order.
FUNCTION_SERIES = [
    ("instruction", "Instruction", ["1000 Instruction"]),
    ("instr_related", "Instruction-related services", ["2000 Instruction-Related Services"]),
    ("pupil", "Pupil services", ["3000 Pupil Services"]),
    ("ancillary", "Ancillary services", ["4000 Ancillary Services"]),
    ("admin", "General administration", ["7000 General Administration"]),
    ("plant", "Plant services", ["8000 Plant Services"]),
    ("other", "Other (community, enterprise, other outgo)",
     ["5000 Community Services", "6000 Enterprise", "9000 Other Outgo"]),
]
KIND_LABELS = {
    "Unrestricted (LCFF)": "Unrestricted (LCFF base + supplemental/concentration)",
    "State restricted (6000s-7000s)": "State restricted (special ed, block grants, pensions)",
    "Federal": "Federal (Title I, IDEA, ...)",
    "State restricted (2000s)": "Expanded Learning Opportunities (state)",
    "Local restricted": "Local restricted (maintenance, other local)",
}


def fold_functions(values: dict[str, float]) -> dict[str, float]:
    return {key: round(sum(values.get(f, 0.0) for f in members), 2)
            for key, _, members in FUNCTION_SERIES}


def _num(v) -> float | None:
    """Blank (NaN) stays None so the page shows "not reported", never 0."""
    return None if pd.isna(v) else round(float(v), 2)


def trend(g: pd.DataFrame) -> list[dict]:
    """One row per year for one district, from the Phase 2 combined dataset."""
    rows = []
    for year, y in g.groupby("year", sort=True):
        first = y.iloc[0]
        spend = y.dropna(subset=["spend_per_pupil"])
        has_spend = not spend.empty
        flag = str(first["data_quality_flag"])
        rows.append({
            "year": year,
            "ada": _num(first["ada"]),
            "spend_total": round(float(y["spend_total"].sum()), 2) if y["spend_total"].notna().any() else None,
            "spend_per_ada": round(float(spend["spend_per_pupil"].sum()), 2) if has_spend else None,
            "per_ada_by_function": fold_functions(dict(zip(spend["function"], spend["spend_per_pupil"].astype(float))))
                                   if has_spend else None,
            "ela": _num(first["ela_pct_met_or_exceeded"]),
            "math": _num(first["math_pct_met_or_exceeded"]),
            "data_status": first["data_status"],
            "flags": [] if flag == "ok" else flag.split(";"),
        })
    return rows


def dollars(cds: CDS, year: str, ada: float) -> dict:
    fiscal, _ = join.year_codes(year)
    gl = sacs_parser.general_ledger(cds, fiscal)
    rev = sacs_statement.revenues(gl)
    matrix = sacs_statement.spending_matrix(gl).drop(index="Total")
    kinds = []
    # Fixed order (KIND_LABELS), not sorted by size, so rows don't jump between years.
    order = [k for k in KIND_LABELS if k in matrix.index] + [k for k in matrix.index if k not in KIND_LABELS]
    for kind, row in matrix.loc[order].iterrows():
        by_fn = fold_functions({c: float(v) for c, v in row.items() if c != "Total"})
        kinds.append({"kind": kind, "label": KIND_LABELS.get(kind, kind),
                      "total": round(float(row["Total"]), 2), "by_function": by_fn})
    top = sacs_statement.top_resources(gl, 12, fiscal)
    # One-time pandemic relief, by resource title within operating spending:
    #   federal = federal resources (3000-5999) naming ESSER, GEER or the American Rescue Plan
    #   state   = 7435 Learning Recovery Emergency Block Grant (one-time state money)
    titles = sacs_parser.code_titles("Resource", fiscal)
    ops = gl[sacs_parser.in_scope(gl)]
    res = ops["Resource"].astype(int)
    relief = [r for r in ops["Resource"].unique() if 3000 <= int(r) <= 5999
              and any(k in titles.get(r, "") for k in ("ESSER", "GEER", "American Rescue Plan"))]
    esser = float(ops[ops["Resource"].isin(relief)]["Value"].sum())
    lr_block = float(ops[res == 7435]["Value"].sum())
    return {
        "federal_relief": round(esser, 2),
        "state_learning_recovery": round(lr_block, 2),
        "year": year,
        "ada": ada,
        "revenues": [{"source": r.source, "amount": round(float(r.amount), 2)} for r in rev.itertuples()],
        "kinds": kinds,
        "top_resources": [{"code": r.Resource, "title": r.title, "kind": r.kind,
                           "amount": round(float(r.amount), 2)} for r in top.itertuples()],
    }


def county() -> pd.DataFrame:
    return pd.read_csv(COUNTY, dtype={"cds": str})


def export(g: pd.DataFrame) -> dict:
    """Write docs/data/<cds>.js for one district; return its picker entry."""
    first = g.iloc[0]
    cds = CDS.parse(first["cds"])
    t = trend(g)
    data = {
        "district": first["district_name"],
        "cds": cds.code,
        "district_type": first["district_type"],
        "verified": cds.code in VERIFIED,
        "generated": date.today().isoformat(),
        "function_series": [{"key": k, "label": label} for k, label, _ in FUNCTION_SERIES],
        "trend": t,
        "dollars": [dollars(cds, row["year"], row["ada"]) for row in t
                    if row["data_status"] in ("both", "missing_caaspp") and row["ada"]],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{cds.code}.js"
    out.write_text("(window.MAIA_DATA = window.MAIA_DATA || {})[" + json.dumps(cds.code) + "] = "
                   + json.dumps(data, indent=1) + ";\n")
    return {"cds": cds.code, "name": data["district"], "type": data["district_type"],
            "years": [r["year"] for r in t], "flagged": any(r["flags"] for r in t)}


def write_index(entries: list[dict]) -> Path:
    """The district picker list, alphabetical. No ordering by any metric."""
    out = OUT_DIR / "index.js"
    entries = sorted(entries, key=lambda e: e["name"].lower())
    out.write_text("window.MAIA_INDEX = " + json.dumps(
        {"generated": date.today().isoformat(), "districts": entries}, indent=1) + ";\n")
    return out


if __name__ == "__main__":
    df = county()
    only = sys.argv[1] if len(sys.argv) > 1 else None
    entries = []
    for code, g in df.groupby("cds", sort=True):
        if only and code != CDS.parse(only).code:
            continue
        entries.append(export(g))
        print(f"  {code} {entries[-1]['name']}")
    if not only:
        print(f"Wrote {len(entries)} district files and {write_index(entries)}")
