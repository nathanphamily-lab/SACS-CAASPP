# Phase 2 — Multi-District Pipeline (All LA County)

Scope note: this builds directly on Phase 1's working, verified single-district pipeline (`sacs_parser.py`, `caaspp_parser.py`, `cds_lookup.py`, `join.py`). Do not rewrite those — extend them. Per the spec doc, this phase still does not include any dashboard or public-facing output (that's Phase 3).

## Goal
The same joined table from Phase 1 (`district_name | year | function | spend_per_pupil | ela_pct_met_or_exceeded | math_pct_met_or_exceeded`), produced for all 80 LA County districts instead of just LAUSD, in one combined dataset.

## Precondition
Phase 1's pipeline must already produce correct, hand-verified output for LAUSD. If anything in Phase 1 was stubbed, hardcoded to LAUSD specifically, or skipped error handling because "it's just one district," fix that first — this phase will immediately expose those shortcuts.

## Task breakdown

### Task 1 — Get the full CDS code list for LA County
Pull CDE's full CDS reference list and filter to LA County's 80 districts (confirmed count from LACOE: ~48 unified, 27 elementary, 5 high school). Output: a clean list of 80 CDS codes with district names, saved as its own reference file — this is the loop's input.

### Task 2 — Generalize `cds_lookup.py`
Phase 1 likely resolved LAUSD's identifier mapping somewhat by hand. This task makes that mapping table-driven: given any CDS code from Task 1's list, resolve its SACS identifier and its CAASPP-side identifier automatically. If some districts don't cleanly resolve (small districts sometimes have inconsistent records), log them — don't silently skip them.

### Task 3 — Loop `sacs_parser.py` and `caaspp_parser.py` across all 80
Run both parsers for every CDS code in the Task 1 list. Expect failures — not every small district will have clean data for every year. Capture per-district success/failure in a log, don't let one bad district crash the whole run.

### Task 4 — Combined dataset
Run `join.py` across all 80 districts' parsed output, producing one combined table (not 80 separate files). Include a `data_quality_flag` column or similar for any district/year where either source was missing or suppressed — don't quietly drop incomplete rows, mark them.

### Task 5 — Validation pass
Spot-check 3-4 districts beyond LAUSD by hand (pick a mix of sizes — one mid-size unified, one small elementary district) against their own published numbers, same way Phase 1's Task 1 worked. This is the main defense against "the pipeline runs without errors but produces wrong numbers for districts we didn't check."

### Task 6 — Known-gap handling
Per the README's noted gotchas: some smaller districts will have CAASPP small-n suppression (scores withheld for privacy when too few students tested). Decide and document how suppressed values are represented in the output (e.g., explicit `null` + flag, not a 0 or a dropped row) — this matters because a 0 would misread as "this district scored zero," which is wrong and could be taken as an accusation.

## Explicitly out of scope for this task
- Any dashboard, chart, or public-facing visualization (Phase 3)
- Statewide expansion beyond LA County's 80 districts
- The "best-practice mirror" or other future-direction variants from the spec doc
- Automated re-running on a schedule (this is a one-time batch run for now)

## Definition of done
One combined, validated dataset covering all 80 LA County districts for the same year range used in Phase 1, with a data-quality flag for incomplete records, and at least 4 districts total (including LAUSD) hand-verified against their own published numbers.
