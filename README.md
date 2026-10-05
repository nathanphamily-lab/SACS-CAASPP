# CA School Spending vs. Outcomes — Build README

Companion to `maia_spending_outcomes_spec.md` (read that first for the "why"). This doc is the "how" — meant to be handed to Claude Code as the starting point for the actual build.

## Current phase
**Phase 0/1**: prove the SACS-to-CAASPP join works for a single district (start with LAUSD, CDS code `19647330000000`), then generalize to a script that takes any CDS code.

## Status (2026-10-02)
Phase 1 is **done** for LAUSD, 2022-23 → 2024-25, per `PHASE1_TASKS.md`. `pytest` passes 47 of 47. See `notes/phase1_signoff.md`.

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python src/join.py --cds 19647330000000 --years 2022-23:2024-25   # the Phase 1 table
.venv/bin/python src/sacs_viewer.py list 19647330000000 2022-23 2023-24 2024-25   # find LAUSD's filings
.venv/bin/python src/sacs_viewer.py ingest 19647330000000                         # file the downloaded ZIPs
.venv/bin/python src/ground_truth.py   # rebuild data/ground_truth/lausd_expected.csv
.venv/bin/pytest -q                    # pipeline vs ground truth
```
Webpage (LAUSD only for now): `docs/index.html`, a static page with a view filter. District trend and Kinds of dollars are built; School explorer and Method & caveats are next. Refresh its data with `.venv/bin/python src/export_web.py`, then open `docs/index.html` in a browser (it also works as-is on GitHub Pages from `docs/`).

Notes: `notes/task2_identifiers.md` (identifiers and schema differences between years), `notes/sacs_viewer_api.md` (how filings are retrieved). Beyond Phase 1, the school-level returns model (`src/school_data.py`, `src/returns_model.py`) was built on request; see `notebooks/phase1b_returns.ipynb`.

## What "done" looks like for Phase 1
Given a CDS code and a year range, the script outputs a table with columns:
`district_name, year, function, spend_per_pupil, ela_pct_met_or_exceeded, math_pct_met_or_exceeded`

That's the whole deliverable for this phase. No dashboard, no UI — just a correct, joined table for one district, provably right by spot-checking against the district's own published numbers.

## Data acquisition — do this first, before writing pipeline code
1. **SACS financial data**: Download the annual SACS `.mdb` file from CDE (e.g. `sacs2425.exe` → extracts to `sacs2425.mdb`) from `https://www.cde.ca.gov/ds/fd/fd/`. This is a Microsoft Access database — will need `mdbtools` (Linux/Mac) or `pyodbc`/`pandas_access` to read it in Python without a Windows/Access environment.
2. **CAASPP data**: Pull district-level results from CDE's CAASPP research files (`caaspp.cde.ca.gov` research file downloads) — these are flat CSV/fixed-width files, much easier to parse than SACS.
3. **CDS code reference**: CDE publishes a full CDS code list (`cde.ca.gov/ds/si/ds/pubschls.asp` or similar) — pull this once and cache it locally; it's the Rosetta Stone between SACS and CAASPP records.

**Do not start writing join logic before confirming, by hand, that both files identify LAUSD using values you can match** — this is the step most likely to quietly fail. Pull LAUSD's row from both raw files first and manually verify the identifiers before writing any automated matching.

## Suggested repo structure
```
/data
  /raw          — downloaded SACS .mdb, CAASPP CSVs, CDS reference list (gitignored, large files)
  /processed    — cleaned, joined output tables
/src
  sacs_parser.py     — reads .mdb, extracts function-level spending by district/year
  caaspp_parser.py   — reads CAASPP files, extracts proficiency % by district/year
  cds_lookup.py      — builds/maintains the CDS-code mapping table
  join.py            — combines the above into the Phase 1 output table
/notebooks
  phase0_lausd.ipynb — the manual, exploratory version for LAUSD (do this before src/ scripts)
maia_spending_outcomes_spec.md
README.md
requirements.txt
```

## Suggested environment
- Python 3.11+
- `pandas`, `mdbtools` or `pandas-access` (for reading SACS .mdb), `requests` (for pulling CDE files)
- SQLite for local storage of the processed/joined table — no need for a full DB server at this phase

## Order of operations (for whoever/whatever builds this)
1. Manually pull and eyeball LAUSD's SACS + CAASPP numbers (Phase 0 — spec doc section 6). Confirm the divergence pattern the team is interested in is actually visible before automating anything.
2. Write `cds_lookup.py` — this is the highest-risk piece; get it right for one district before scaling.
3. Write `sacs_parser.py` and `caaspp_parser.py` independently — each should work standalone and be testable against known LAUSD numbers.
4. Write `join.py` to combine them for one CDS code.
5. Only once step 4 works correctly for LAUSD: generalize to loop over all 80 LA County CDS codes (Phase 2, not this phase — don't jump ahead).

## Known gotchas (from research so far)
- SACS `.mdb` files vary in exact schema year to year — don't hardcode column assumptions across years without checking each year's readme.
- CAASPP methodology changed with the SBAC transition (~2015) — don't pull years before that into the same trend line without flagging the discontinuity.
- Some smaller LA County districts may have incomplete or suppressed CAASPP data (small n suppression) — the pipeline needs to handle missing/null gracefully, not error out.

## What NOT to build yet
No dashboard, no public site, no multi-district loop, no "best practice mirror" variant — those are Phase 2/3/future-directions per the spec doc. Phase 1 success is one correct, verifiable table for one district.
