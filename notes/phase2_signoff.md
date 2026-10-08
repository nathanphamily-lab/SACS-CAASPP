# Phase 2 sign-off — all LA County districts, 2022-23 → 2024-25

**Status: done per `PHASE2_TASKS.md`.** `pytest` passes 114 of 114 (2026-10-05).

```
.venv/bin/python src/la_county.py     # the 79-district list
.venv/bin/python src/run_county.py    # combined dataset + logs (~4 min first time, then ~15 s)
.venv/bin/pytest -q
```

## Output
`data/processed/la_county_2223-2425.csv` (also a SQLite table in `maia.sqlite`):
- 79 districts × 3 years = 237 district-years, 1,543 rows (one per SACS function group).
- The Phase 1 columns, plus `cds`, `district_type`, `spend_total`, `ada` (with its `k12_ada` and `fund01_charter_ada` parts), `data_status` and `data_quality_flag`.
- Logs: `run_log.csv` (474 steps, 0 failed) and `resolution_log.csv` (the name each source gives each district).

## Tasks
| Task | Result |
|---|---|
| 1. District list | `data/reference/la_county_districts.csv`: **79** districts (48 unified, 26 elementary, 5 high school) from CDE's directory. It matches SACS exactly in every year. The task doc's "80" doesn't match either source. LACOE, 11 ROC/Ps and 9 JPAs are excluded as not school districts. |
| 2. Table-driven lookup | `cds_lookup.resolve()` checks every district in the directory, SACS and CAASPP for each year. All resolve. Name differences are only SACS's "Elementary" suffix, which is cosmetic. |
| 3. Loop | `sacs_parser.extract_county()` parses each year once (~80 s) instead of once per district (~4.5 h in total). `join.build_many()` isolates failures per district-year. |
| 4. Combined table | One file, with a data-quality flag on every row. |
| 5. Validation | 4 districts checked against their own filings (below). |
| 6. Known gaps | `notes/phase2_data_quality.md`: unavailable scores are null plus a flag, never 0. |

## Hand-verified districts
| District | Type | 2024-25 ADA | Checked against | Result |
|---|---|---|---|---|
| Los Angeles Unified | Unified (largest) | 371,342 | Form 01 + Form A, 3 years; CAASPP site, 3 years | Matches to the cent, except one documented 2023-24 line (`known_differences.csv`) |
| Redondo Beach Unified | Unified (mid-size) | 9,008 | Form 01 + Form A, 2024-25; CAASPP site, 3 years | Matches to the cent on every line |
| Hughes-Elizabeth Lakes Union Elementary | Elementary (small) | 184 | Form 01 + Form A, 2024-25; CAASPP site, 3 years | Matches to the cent on every line |
| Whittier Union High | High school | 9,172 | Form 01 + Form A, 2024-25; CAASPP site, 3 years | Matches to the cent on every line |

Hughes-Elizabeth Lakes has the county's lowest spending per student ($14,481 in 2024-25), which is unusual for a very small district. Its own filing confirms it: General Fund expenditures of $2,668,090.38 on 184.25 ADA.

## Caveats
- **Suppression:** no district-level CAASPP score was suppressed in LA County in any year (the smallest district had 55 tested). The handling is covered by a synthetic test.
- **Comparisons across district types are left to Phase 3.** Unified, elementary and high-school districts test different grades and have different cost structures. `district_type` is in the data for that.
- **Fund 01 charter ADA:** the Phase 1 denominator fix applies to LAUSD and Inglewood Unified only.
- **Filings layout:** filings now live in `data/raw/filings/<cds>/<year>/`. LAUSD's moved there from `data/raw/lausd_filings/`.
