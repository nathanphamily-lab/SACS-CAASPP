"""Phase 2, Task 1: the list of LA County school districts the county run loops over.

    python src/la_county.py      # writes data/reference/la_county_districts.csv

Source: CDE's public districts directory (data/raw/cde/pubdistricts.txt): county 19, Active,
DOCType unified / elementary / high school district. That gives 79 (48 / 26 / 5). Excluded by
design: LACOE (county office), ROC/Ps, and JPAs, which aren't school districts and have no ADA.

Each year's SACS LEAs table is cross-checked against the list; any district missing from
SACS, or a SACS school district missing from the directory, is reported, not silently dropped.
"""
from pathlib import Path

import pandas as pd

import sacs_parser
from cds_lookup import directory

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reference" / "la_county_districts.csv"
COUNTY = "19"
DISTRICT_TYPES = {
    "Unified School District": "Unified",
    "Elementary School District": "Elementary",
    "High School District": "High School",
}
SACS_TYPES = {"Unified School District", "Elementary School District", "High School District"}
FISCAL_YEARS = ["2223", "2324", "2425"]


def district_list() -> pd.DataFrame:
    d = directory()
    d = d[d["CD Code"].str.startswith(COUNTY) & (d["StatusType"] == "Active")
          & d["DOCType"].isin(DISTRICT_TYPES)]
    out = pd.DataFrame({
        "cds": d["CD Code"] + "0000000",
        "district_name": d["District"],
        "district_type": d["DOCType"].map(DISTRICT_TYPES),
    })
    return out.sort_values("district_name").reset_index(drop=True)


def sacs_districts(fiscal: str) -> set[str]:
    t = sacs_parser._small_table(fiscal, "LEAs")
    w = sacs_parser.widths(fiscal)
    return {t["Ccode"][i][:2] + t["Dcode"][i][:5] + "0000000" for i in range(len(t["Ccode"]))
            if t["Ccode"][i][:2] == COUNTY and t["Dtype"][i][:w["Dtype"]].strip() in SACS_TYPES}


def cross_check(districts: pd.DataFrame) -> list[str]:
    issues = []
    ours = set(districts["cds"])
    for fy in FISCAL_YEARS:
        sacs = sacs_districts(fy)
        issues += [f"{fy}: {c} in directory but not a SACS school district" for c in sorted(ours - sacs)]
        issues += [f"{fy}: {c} is a SACS school district but not in the directory list" for c in sorted(sacs - ours)]
    return issues


if __name__ == "__main__":
    df = district_list()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"{len(df)} districts -> {OUT}")
    print(df["district_type"].value_counts().to_string())
    issues = cross_check(df)
    print("\nSACS cross-check:", "no differences in " + ", ".join(FISCAL_YEARS) if not issues else "")
    for i in issues:
        print("  ", i)
