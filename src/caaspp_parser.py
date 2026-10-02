"""CAASPP Smarter Balanced research file -> ELA/math % met or exceeded for one entity.

Input: the caret-delimited "All Students" statewide file (sb_ca{YYYY}_1_csv_v1.txt)
from caaspp-elpac.ets.org research files. YYYY is the spring test year,
so the 2024-25 school year is 2025.
"""
from pathlib import Path

import pandas as pd

from cds_lookup import CDS, RAW

TEST_IDS = {"1": "ela", "2": "math"}  # Tests.txt
ALL_STUDENTS = "1"  # StudentGroups.txt: Demographic ID Num 1 = All Students
ALL_GRADES = "13"  # grade 13 = all grades combined
PCT_COL = "Percentage Standard Met and Above"


def to_pct(value: str) -> float | None:
    """Parse a percentage. Returns None for suppressed or blank values ('*', '')."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def proficiency(cds: CDS, test_year: str = "2025") -> dict:
    path = RAW / "caaspp" / f"sb_ca{test_year}_1_csv_v1.txt"
    df = pd.read_csv(path, sep="^", dtype=str, keep_default_na=False, encoding="latin-1")
    rows = df[
        (df["County Code"] == cds.county)
        & (df["District Code"] == cds.district)
        & (df["School Code"] == cds.school)
        & (df["Student Group ID"] == ALL_STUDENTS)
        & (df["Grade"] == ALL_GRADES)
        & (df["Test ID"].isin(TEST_IDS))
    ]
    out = {f"{name}_pct_met_or_exceeded": None for name in TEST_IDS.values()}
    for _, r in rows.iterrows():
        out[f"{TEST_IDS[r['Test ID']]}_pct_met_or_exceeded"] = to_pct(r[PCT_COL])
    return out


if __name__ == "__main__":
    import sys

    print(proficiency(CDS.parse(sys.argv[1] if len(sys.argv) > 1 else "19647330000000")))
