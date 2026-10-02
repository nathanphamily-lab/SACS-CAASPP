"""District-level SACS statement: where the money comes from and which kinds of dollars
pay for which functions.

"Kind of dollar" = SACS resource-code range (funding source restriction):
  0000-1999 unrestricted (LCFF base + supplemental/concentration, lottery, etc.)
  2000-2999 state restricted, newer programs (e.g. 2600 Expanded Learning Opportunities)
  3000-5999 federal (e.g. 3010 Title I, 3310 IDEA special ed)
  6000-7999 state restricted (e.g. 6500 special ed)
  8000-9999 local restricted
"""
import pandas as pd

import sacs_parser
from cds_lookup import CDS

KINDS = [
    (0, 1999, "Unrestricted (LCFF)"),
    (2000, 2999, "State restricted (2000s)"),
    (3000, 5999, "Federal"),
    (6000, 7999, "State restricted (6000s-7000s)"),
    (8000, 9999, "Local restricted"),
]
REVENUE_SOURCES = [
    ("8010", "8099", "LCFF sources"),
    ("8100", "8299", "Federal revenue"),
    ("8300", "8599", "Other state revenue"),
    ("8600", "8799", "Other local revenue"),
]


def kind_of_dollar(resource: pd.Series) -> pd.Series:
    r = resource.astype(int)
    out = pd.Series(pd.NA, index=resource.index, dtype="string")
    for lo, hi, name in KINDS:
        out[r.between(lo, hi)] = name
    return out


def revenues(gl: pd.DataFrame) -> pd.DataFrame:
    f = gl[gl["Fund"] == sacs_parser.FUND]
    rows = [(name, float(f[f["Object"].between(lo, hi)]["Value"].sum()))
            for lo, hi, name in REVENUE_SOURCES]
    return pd.DataFrame(rows, columns=["source", "amount"])


def spending_matrix(gl: pd.DataFrame) -> pd.DataFrame:
    """In-scope operating spending: kind of dollar (rows) x function group (columns)."""
    sel = gl[sacs_parser.in_scope(gl)].copy()
    sel["kind"] = kind_of_dollar(sel["Resource"])
    sel["function"] = sel["Function"].str[0].map(sacs_parser.FUNCTION_GROUPS)
    sel["amount"] = sel["Value"].map(float)
    m = sel.pivot_table(index="kind", columns="function", values="amount", aggfunc="sum", fill_value=0)
    m["Total"] = m.sum(axis=1)
    m.loc["Total"] = m.sum()
    return m


def top_resources(gl: pd.DataFrame, n: int = 12) -> pd.DataFrame:
    sel = gl[sacs_parser.in_scope(gl)]
    out = sel.groupby("Resource")["Value"].sum().map(float).sort_values(ascending=False).head(n)
    out = out.rename("amount").reset_index()
    titles = sacs_parser.code_titles("Resource")
    out.insert(1, "title", out["Resource"].map(titles))
    out.insert(2, "kind", kind_of_dollar(out["Resource"]))
    return out


if __name__ == "__main__":
    cds = CDS.parse("19647330000000")
    gl = sacs_parser.general_ledger(cds)
    fmt = lambda v: f"${v / 1e6:,.1f}M"
    print("General Fund revenues\n", revenues(gl).assign(amount=lambda d: d.amount.map(fmt)).to_string(index=False))
    print("\nOperating spending: kind of dollar x function\n", spending_matrix(gl).map(fmt).to_string())
    print("\nLargest resources\n", top_resources(gl).assign(amount=lambda d: d.amount.map(fmt)).to_string(index=False))
