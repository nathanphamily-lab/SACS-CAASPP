# Phase 2 — data-quality rules (Task 6)

Applies to `data/processed/la_county_2223-2425.csv`: 79 LA County districts × 2022-23 → 2024-25, built by `src/run_county.py`.

## Rules
- **Rows are never dropped.** Every district × year from `data/reference/la_county_districts.csv` appears. A year missing from one source gets a single row with blank spending (or blank scores) and a flag.
- **Unavailable scores are blank (null), never 0.** A 0 would read as "no student met the standard," which is false and could look like an accusation.
- **`data_quality_flag`** lists every issue for that district-year, separated by `;`, or `ok`:

| Flag | Meaning |
|---|---|
| `missing_sacs` / `missing_caaspp` | that year is absent from one source |
| `ela_suppressed` / `math_suppressed` | CAASPP has a row, but the score is withheld (e.g. `*`) because too few students tested |
| `ela_no_record` / `math_no_record` | CAASPP has no row for the district that year |
| `ada_zero` | no ADA, so `spend_per_pupil` is blank |
| `name_mismatch` | SACS or CAASPP names the district differently from CDE's directory, ignoring a trailing type word like "Elementary" |

- **Every step is logged.** `run_log.csv` has one row per district × year × source (`ok` or the error). `resolution_log.csv` shows the name each source gives each district in each year.

## Results of the 2026-10-05 run
- **Flags:** all 237 district-years are `ok`, and all 474 run steps succeeded.
- **Suppression:** none. The smallest district-level CAASPP result had 55 students tested (2023), above the suppression threshold. The suppression path is covered by a synthetic test (`tests/test_county.py::test_suppressed_score_is_null_and_flagged`).
- **Names:** 9 elementary districts appear as "<Name> Elementary" in SACS but "<Name>" in CDE's directory, and CAASPP 2023 does the same for Whittier City. The codes match in every source, so these are cosmetic and not flagged.
- **Fund 01 charter ADA** (the Phase 1 fix) applies to 2 districts: LAUSD and Inglewood Unified (`19646340000000`). Everyone else's ADA is the SACS K-12 ADA alone.

## Not handled here (by decision)
- **Comparisons across district types (Phase 3).** Unified, elementary (K-8) and high-school (9-12) districts have different cost structures and test different grades. `district_type` is carried in the data for that.
- **School-level suppression:** not used in this dataset.
