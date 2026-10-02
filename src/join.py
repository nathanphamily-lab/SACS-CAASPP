"""Phase 1: join SACS spending-by-function with CAASPP proficiency for ONE district over a
range of years.

    python src/join.py --cds 19647330000000 --years 2022-23:2024-25
    python src/join.py --cds 19647330000000 --year 2024-25      # single-year shorthand

Years are joined on `year` with an outer join. A year present in only one source is kept
and flagged in `data_status` (both / missing_sacs / missing_caaspp), never dropped.

Output: data/processed/<cds>_<first>-<last>.csv and a table in data/processed/maia.sqlite.
"""
import argparse
import sqlite3
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

import caaspp_parser
import sacs_parser
from cds_lookup import CDS, caaspp_entity, directory_record

PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"
COLUMNS = ["district_name", "year", "function", "spend_per_pupil",
           "ela_pct_met_or_exceeded", "math_pct_met_or_exceeded"]
EXTRA = ["spend_total", "ada", "k12_ada", "fund01_charter_ada", "data_status"]
SCORE_COLS = ["ela_pct_met_or_exceeded", "math_pct_met_or_exceeded"]


def year_codes(year: str) -> tuple[str, str]:
    """'2024-25' -> SACS fiscal code '2425', CAASPP test year '2025'."""
    start, end = year.split("-")
    return start[2:] + end[-2:], start[:2] + end[-2:]


def year_range(spec: str) -> list[str]:
    """'2022-23:2024-25' -> ['2022-23', '2023-24', '2024-25']."""
    first, _, last = spec.partition(":")
    last = last or first
    a, b = int(first[:4]), int(last[:4])
    if b < a:
        raise ValueError(f"bad year range {spec!r}")
    return [f"{y}-{str(y + 1)[2:]}" for y in range(a, b + 1)]


def sacs_year(cds: CDS, year: str) -> pd.DataFrame | None:
    """function, spend_total and ADA for one year, or None if that year's SACS file is absent.
    `ada` = district K-12 ADA + ADA of charters reported in the district's Fund 01."""
    fiscal, _ = year_codes(year)
    if not (sacs_parser.RAW / f"sacs{fiscal}.mdb").exists():
        return None
    lea = sacs_parser.lea(cds, fiscal)
    df = sacs_parser.spending_by_function(cds, fiscal).rename(columns={"spend": "spend_total"})
    df["spend_total"] = df["spend_total"].map(float)
    return df.assign(ada=lea["ada"], k12_ada=lea["k12_ada"],
                     fund01_charter_ada=lea["fund01_charter_ada"], sacs_name=lea["district_name"])


def caaspp_year(cds: CDS, year: str) -> dict | None:
    """ELA/math % met or exceeded for one year, or None if that year's CAASPP file is absent."""
    _, test_year = year_codes(year)
    if not (caaspp_parser.RAW / "caaspp" / f"sb_ca{test_year}_1_csv_v1.txt").exists():
        return None
    scores = caaspp_parser.proficiency(cds, test_year)
    scores["caaspp_name"] = caaspp_entity(cds, test_year)["District Name"]
    return scores


def combine(district_name: str, spend: dict[str, pd.DataFrame | None],
            scores: dict[str, dict | None]) -> pd.DataFrame:
    """Outer-join per-year spending (rows by function) with per-year scores."""
    rows = []
    for year in sorted(set(spend) | set(scores)):
        s, c = spend.get(year), scores.get(year)
        status = "both" if s is not None and c is not None else (
            "missing_caaspp" if s is not None else "missing_sacs")
        cols = ["function", "spend_total", "ada", "k12_ada", "fund01_charter_ada"]
        base = s[cols].copy() if s is not None else pd.DataFrame({c: [np.nan] for c in cols})
        for col in SCORE_COLS:
            base[col] = c[col] if c is not None else np.nan
        rows.append(base.assign(year=year, data_status=status))
    out = pd.concat(rows, ignore_index=True).assign(district_name=district_name)
    out["spend_per_pupil"] = (out["spend_total"] / out["ada"]).round(2)
    return out[COLUMNS + EXTRA]


def build(cds: CDS, years: list[str]) -> pd.DataFrame:
    if not cds.is_district:
        raise ValueError("Phase 1 is district-level only (school code must be 0000000)")
    name = directory_record(cds)["District"]

    spend = {y: sacs_year(cds, y) for y in years}
    scores = {y: caaspp_year(cds, y) for y in years}
    # Guard against a silent identifier mismatch: every source must name the same district.
    for y in years:
        for label, got in [("SACS", spend[y]["sacs_name"].iloc[0] if spend[y] is not None else None),
                           ("CAASPP", scores[y]["caaspp_name"] if scores[y] is not None else None)]:
            if got is not None and got != name:
                raise ValueError(f"{y}: {label} names {got!r}, CDE directory names {name!r}")

    table = combine(name, spend, scores)
    for y, status in table.groupby("year")["data_status"].first().items():
        if status != "both":
            warnings.warn(f"{y}: {status}; row kept and flagged, not dropped")
    return table


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cds", default="19647330000000")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--years", help="range, e.g. 2022-23:2024-25")
    g.add_argument("--year", help="single year, e.g. 2024-25")
    args = ap.parse_args()

    cds = CDS.parse(args.cds)
    years = year_range(args.years or args.year or "2022-23:2024-25")
    table = build(cds, years)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    first, last = year_codes(years[0])[0], year_codes(years[-1])[0]
    stem = f"{cds.code}_{first}" if first == last else f"{cds.code}_{first}-{last}"
    table.to_csv(PROCESSED / f"{stem}.csv", index=False)
    with sqlite3.connect(PROCESSED / "maia.sqlite") as con:
        table.to_sql(f"phase1_{stem.replace('-', '_')}", con, if_exists="replace", index=False)

    pd.set_option("display.width", 200)
    print(table.to_string(index=False))
    print("\nTotal in-scope spend per ADA (district + Fund 01 charter ADA) by year:")
    print(table.groupby("year")["spend_per_pupil"].sum().map("${:,.2f}".format).to_string())
    print(f"Wrote {PROCESSED / (stem + '.csv')}")


if __name__ == "__main__":
    main()
