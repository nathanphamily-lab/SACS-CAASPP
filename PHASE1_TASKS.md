# Phase 1 — Single-District SACS/CAASPP Pipeline

Scope note: this is Phase 1 only (per README.md and the spec doc). Do not build Phase 2 (multi-district loop) or Phase 3 (dashboard) as part of this task. Target district for this phase: **LAUSD**, CDS code `19647330000000`.

## Goal
Given one CDS code and a year range, produce one correct, verifiable table:

`district_name | year | function | spend_per_pupil | ela_pct_met_or_exceeded | math_pct_met_or_exceeded`

"Correct" means: every number in that table can be manually spot-checked against LAUSD's own published SACS filing and CAASPP results and match.

## Task breakdown

### Task 1 — Manual ground truth (do this before writing any parser code)
Pull LAUSD's raw SACS filing and CAASPP results by hand for 2-3 recent years. Write down the actual numbers you expect the pipeline to produce. This is the test fixture everything else gets checked against — skipping this step means you won't know if the pipeline is wrong until much later.

### Task 2 — CDS/identifier reconciliation
Confirm how LAUSD is identified in each raw file:
- SACS `.mdb`: which field holds the district identifier, and what does LAUSD's value look like?
- CAASPP file: same question, for its own ID system.
- CDE's CDS reference list: confirm it contains both, and can bridge them.

Output of this task: a written note (a few lines) documenting the exact field names and LAUSD's values in each, so `cds_lookup.py` isn't guessing.

### Task 3 — `sacs_parser.py`
Input: SACS `.mdb` file + a CDS code.
Output: a table of `year, function, spend_total, enrollment` (or `spend_per_pupil` if enrollment is joinable at this stage) for that district only.
Test: run against LAUSD, compare to Task 1's ground truth.

### Task 4 — `caaspp_parser.py`
Input: CAASPP research file(s) + a CDS code (or its CAASPP-side equivalent, via Task 2's mapping).
Output: `year, ela_pct_met_or_exceeded, math_pct_met_or_exceeded` for that district.
Test: run against LAUSD, compare to Task 1's ground truth.

### Task 5 — `join.py`
Combine Task 3 + Task 4 output on `year` for the single CDS code. Handle the case where a year exists in one dataset but not the other (don't silently drop — flag it).
Output: the final table described in "Goal" above.

### Task 6 — Sanity check
Run the full pipeline for LAUSD end to end. Confirm every row matches Task 1's manual numbers. If anything's off, the bug is almost certainly in Task 2 (identifier mismatch) or a year-over-year schema change in the SACS file — check those first before assuming the math is wrong.

## Explicitly out of scope for this task
- Looping over multiple districts
- Any visualization or dashboard
- Handling CAASPP small-n suppression edge cases (note them if encountered, but don't build handling yet — that's Phase 2)
- Function-level granularity beyond what SACS reports natively (don't invent categories)

## Definition of done
One script (or notebook) that takes `cds_code` and `year_range` as input and outputs the joined table for LAUSD, with every value verified by hand against Task 1.
