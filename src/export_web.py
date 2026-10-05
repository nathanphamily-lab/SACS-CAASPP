"""Export the data behind the static webpage (docs/index.html) for one district.

    python src/export_web.py                       # LAUSD, 2022-23 → 2024-25

Writes docs/data/<cds>.js, which sets `window.MAIA_DATA`. A .js file (not .json) so the page
works both when opened straight from disk (file://, where fetch() is blocked) and on GitHub
Pages. Every number comes from the verified Phase 1 modules; nothing is recomputed here.
"""
import json
import sys
from datetime import date
from pathlib import Path

import join
import sacs_parser
import sacs_statement
from cds_lookup import CDS

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "data"

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


def trend(cds: CDS, years: list[str]) -> list[dict]:
    table = join.build(cds, years)
    rows = []
    for year, g in table.groupby("year", sort=True):
        first = g.iloc[0]
        rows.append({
            "year": year,
            "ada": float(first["ada"]),
            "spend_total": round(float(g["spend_total"].sum()), 2),
            "spend_per_ada": round(float(g["spend_per_pupil"].sum()), 2),
            "per_ada_by_function": fold_functions(dict(zip(g["function"], g["spend_per_pupil"].astype(float)))),
            "ela": None if first["ela_pct_met_or_exceeded"] != first["ela_pct_met_or_exceeded"] else float(first["ela_pct_met_or_exceeded"]),
            "math": None if first["math_pct_met_or_exceeded"] != first["math_pct_met_or_exceeded"] else float(first["math_pct_met_or_exceeded"]),
            "data_status": first["data_status"],
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


def export(cds: CDS, years: list[str]) -> Path:
    t = trend(cds, years)
    data = {
        "district": join.directory_record(cds)["District"],
        "cds": cds.code,
        "generated": date.today().isoformat(),
        "function_series": [{"key": k, "label": label} for k, label, _ in FUNCTION_SERIES],
        "trend": t,
        "dollars": [dollars(cds, row["year"], row["ada"]) for row in t if row["data_status"] in ("both", "missing_caaspp")],
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{cds.code}.js"
    out.write_text("window.MAIA_DATA = " + json.dumps(data, indent=1) + ";\n")
    return out


if __name__ == "__main__":
    cds = CDS.parse(sys.argv[1] if len(sys.argv) > 1 else "19647330000000")
    years = join.year_range(sys.argv[2] if len(sys.argv) > 2 else "2022-23:2024-25")
    path = export(cds, years)
    print(f"Wrote {path} ({path.stat().st_size:,} bytes)")
