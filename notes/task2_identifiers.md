# Task 2 — How LAUSD is identified in each source

LAUSD's CDS code is **`19647330000000`**: county `19`, district `64733`, school `0000000` (district level). No source uses a separate ID system, so no crosswalk table is needed. Checked 2026-09-30, and enforced by `tests/test_lausd_ground_truth.py::test_identifiers_agree_across_sources`.

| Source | File | Field(s) | LAUSD value | Name field → value |
|---|---|---|---|---|
| CDE directory | `data/raw/cde/pubdistricts.txt` ("Public Districts" TXT, cde.ca.gov/ds/si/ds/pubschls.asp) | `CD Code` (7 digits = county + district) | `1964733` | `District` → Los Angeles Unified (StatusType Active, DOCType Unified School District) |
| SACS 2022-23, 2023-24, 2024-25 | `sacs{2223,2324,2425}.mdb`, table `LEAs` | `Ccode` (2), `Dcode` (5) | `19`, `64733` | `Dname` → Los Angeles Unified |
| SACS general ledger | same files, table `UserGL` | `Ccode`, `Dcode`, `SchoolCode` (7) | `19`, `64733`, `0000000` for district rows (charter-school rows carry their own school code) | — |
| CAASPP 2023, 2024, 2025 | `sb_ca{2023,2024,2025}_1_csv_v1.txt` | `County Code`, `District Code`, `School Code` | `19`, `64733`, `0000000` | entities file `District Name` → Los Angeles Unified (`Type ID` 6 = district) |

**Year-to-year schema differences found** (the task doc's second suspect after identifiers):
- **SACS `LEAs.Dname`** is 75 characters wide in 2022-23 and 2023-24, and 100 in 2024-25. `sacs_parser.TEXT_WIDTHS` is per year, and an unlisted year raises `SchemaError`.
- **CAASPP 2023** uses a different column order: no name columns, and `Students with Scores` in place of `Total Students Tested with Scores`. The pipeline reads columns by name, so all the columns it uses are unaffected.

**Not recorded here:** LAUSD's NCES district ID. It's only in the full Public Schools file (`NCESDist`), and Chrome blocked that second download from the CDE site. It isn't needed for the SACS–CAASPP join, and it's worth adding when the CCD cross-check from the spec is built.
