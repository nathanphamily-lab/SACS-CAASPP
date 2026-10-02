# Phase 1 sign-off — LAUSD (CDS 19647330000000), 2022-23 → 2024-25

**Status: done per `PHASE1_TASKS.md`.** `pytest` passes 47 of 47 (2026-10-02).

```
.venv/bin/python src/join.py --cds 19647330000000 --years 2022-23:2024-25
```

| Year | General Fund operating spend | ADA (district + Fund 01 charters) | Spend per ADA | ELA % met+ | Math % met+ | data_status |
|---|---|---|---|---|---|---|
| 2022-23 | $9,290.1M | 383,659.84 | $24,214 | 41.17 | 30.50 | both |
| 2023-24 | $10,385.3M | 380,925.11 | $27,263 | 43.06 | 32.83 | both |
| 2024-25 | $10,958.2M | 371,342.10 | $29,510 | 46.45 | 36.76 | both |

The full table, with one row per SACS function group, is `data/processed/19647330000000_2223-2425.csv`.

## What each number was checked against
- **Spending by function:** LAUSD's board-approved Unaudited Actuals, Form 01 "Expenditures by Function" (from CDE's SACS Data Viewer). It matches **to the cent on every line in every year**, with one documented exception in 2023-24, below.
- **Decoding the SACS file:** each year's General Fund total in the `.mdb` equals CDE's state total in `UserGL_Totals` to the cent.
- **ADA:** LAUSD's Form A (Annual ADA). Line A4, district regular ADA, matches SACS `LEAs.K12ADA`; line C4, Fund 01 charter ADA, matches the SACS `Charters` table. The 2024-25 sum equals CDE's Current Expense of Education ADA (371,342.10).
- **Scores:** the CAASPP results site for LAUSD, all students, all grades, each year. Within 0.01, because the site rounds.
- **Identifiers:** see `notes/task2_identifiers.md`.

## Known differences and caveats
1. **One reclassified line in 2023-24.** $1,734,265.00 of object 5800 is function 2700 in CDE's `sacs2324.mdb` but 7200 in LAUSD's filed ledger (`DatExport.dat`). The totals are identical, and the pipeline uses CDE's file. It's recorded in `data/ground_truth/known_differences.csv`, and the test allows only that exact amount.
2. **ADA correction made during this phase.** Before 2026-10-02 the denominator was `LEAs.K12ADA` alone, which overstated per-ADA spending by about 10% ($32,570, now $29,510, for 2024-25). The spending includes 51 affiliated charters reported in Fund 01, but `K12ADA` excludes their ADA.
3. **Spending scope:** objects 1000–5999 plus 7300–7399, a project choice. It is narrower than Form 01's total (which also includes capital outlay and other outgo). 2024-25 is $10,958M vs CDE's Current Expense of Education at $10,877M, a 0.7% gap from definitions only.
4. **Small-group suppression** in CAASPP is noted, not handled. Suppressed values come through blank; that's Phase 2.

## Not in Phase 1 (deliberately)
- Other districts.
- The CCD/NCES cross-check.
- Any dashboard.

The school-level returns model (`src/returns_model.py`) was built on request. It uses ESSA school spending, not this table, so the ADA correction doesn't affect it.
