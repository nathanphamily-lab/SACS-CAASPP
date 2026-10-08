"""Phase 2: run the pipeline for every LA County district and write one combined dataset.

    python src/la_county.py      # once: the district list
    python src/run_county.py     # all 79 districts, 2022-23 -> 2024-25

Prerequisite for speed: sacs_parser.extract_county(fiscal) for each year (one ~70s parse per
year instead of one per district); run_county does it automatically for any year whose
county caches are missing.

Outputs (data/processed/):
  la_county_2223-2425.csv   one row per district x year x function, with data_quality_flag
  run_log.csv               per district/year/step: ok or the error
  resolution_log.csv        per district/year: the name each source gives it
"""
from pathlib import Path

import pandas as pd

import join
import sacs_parser
from cds_lookup import CDS, resolve
from la_county import OUT as DISTRICT_LIST

PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"
YEARS = join.year_range("2022-23:2024-25")


def ensure_caches(districts: pd.DataFrame) -> None:
    for y in YEARS:
        fiscal, _ = join.year_codes(y)
        missing = [c for c in districts["cds"]
                   if not (sacs_parser.CACHE / f"usergl_{fiscal}_{c[:7]}.csv").exists()]
        if missing and (sacs_parser.RAW / f"sacs{fiscal}.mdb").exists():
            print(f"  extracting county ledgers for {fiscal} ({len(missing)} missing)...")
            sacs_parser.extract_county(fiscal)


def main() -> None:
    districts = pd.read_csv(DISTRICT_LIST, dtype=str)
    ensure_caches(districts)

    res = pd.DataFrame([{"year": y, "district_list_name": d.district_name,
                         **resolve(CDS.parse(d.cds), *join.year_codes(y))}
                        for d in districts.itertuples() for y in YEARS])
    table, log = join.build_many(districts, YEARS)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    stem = f"la_county_{join.year_codes(YEARS[0])[0]}-{join.year_codes(YEARS[-1])[0]}"
    table.to_csv(PROCESSED / f"{stem}.csv", index=False)
    log.to_csv(PROCESSED / "run_log.csv", index=False)
    res.to_csv(PROCESSED / "resolution_log.csv", index=False)
    import sqlite3
    with sqlite3.connect(PROCESSED / "maia.sqlite") as con:
        table.to_sql(stem, con, if_exists="replace", index=False)

    per_dy = table.groupby(["cds", "year"])["data_quality_flag"].first()
    print(f"{table['cds'].nunique()} districts, {len(per_dy)} district-years, {len(table)} rows -> {stem}.csv")
    print(f"run log: {int((~log['ok']).sum())} failed steps of {len(log)}")
    flags = per_dy.str.split(";").explode().value_counts()
    print("district-years by flag:\n" + flags.to_string())


if __name__ == "__main__":
    main()
