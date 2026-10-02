# CA School District Spending-vs-Outcomes Tool — Project Spec

## 1. One-line summary
A transparency tool that joins California public school district financial data (SACS) with student outcome data (CAASPP, and later CRDC/attendance) at the district level, to surface where spending and outcomes appear decoupled — for public awareness, not enforcement.

## 2. Problem statement
California doesn't lack school financial or outcome data — SACS gives every district's spending broken down by fund, function, and object, and CAASPP gives every district's test outcomes. What doesn't exist is anyone routinely putting the two side by side at the district level to ask "for what we're spending here, are we getting a reasonable return?" State-level oversight is compliance-focused (did the district spend grant money on what it was earmarked for), not outcome-focused. The 2021 state audit finding that CDE lacked adequate oversight of ESSER/GEER COVID relief spending is a documented example of that gap.

## 3. Goals
- Join district-level SACS spending data with CAASPP outcome data across multiple years.
- Make the join reliable and repeatable across any CA district, not just a hand-picked few.
- Surface cases where spending and outcomes visibly diverge (either direction) for further public/journalistic investigation.
- Ship something demoable in weeks, not a semester-long buildout.

## 4. Explicit non-goals
- **Not a fraud investigation.** No allegations, no claims of wrongdoing.
- **Not a claim that spending doesn't matter.** The empirical relationship between spending and outcomes is genuinely contested in the literature — this tool doesn't take a side, it surfaces cases for others to investigate.
- **Not selling data or access.** No monetization; output should be public/shareable.
- Not attempting statewide coverage in v1 — LA County only to start (80 districts, tractable universe).

## 5. Data sources
| Source | What it provides | Join key | Access method |
|---|---|---|---|
| SACS (CDE) | District financial data by Fund/Resource/Goal/Function/Object | CDS code (14-digit) | Annual .mdb download from cde.ca.gov/ds/fd/fd/ |
| CAASPP (CDE) | ELA/math proficiency by grade, district, year | CDS code (own ID system — needs mapping) | CAASPP public research files / EdSource aggregation |
| CCD (NCES) | Enrollment, demographics, cross-check on district identity | NCES district ID (maps to CDS) | nces.ed.gov/ccd |
| CRDC (future) | Discipline rates, advanced coursework access, teacher experience | School/district level | civilrightsdata.ed.gov |

**Known friction point:** SACS and CAASPP use different ID systems. CDS codes (County-District-School, 14-digit) are the CDE standard and should be the canonical join key; CAASPP data will need to be mapped to CDS codes, which may require a lookup table maintained separately.

## 6. Phased build plan

### Phase 0 — Manual proof of concept (this week)
Pick 2-3 LA County districts of different sizes (e.g., LAUSD + one mid-size + one small). Manually pull SACS spending by function and CAASPP proficiency trends for the same years. Confirm the divergence pattern is real and findable by hand before writing any code.

### Phase 1 — Scripted single-district pipeline
Given one CDS code, script pulls that district's SACS spending-by-function history and CAASPP ELA/math trend, outputs a joined table/chart. Proves the join logic works end-to-end for one district.

### Phase 2 — Multi-district, repeatable pipeline
Extend Phase 1 to loop over all 80 LA County CDS codes. Output: a single dataset (spending-by-function + outcome trend, per district, per year) that can be queried or visualized.

### Phase 3 (stretch) — Presentation layer
A public-facing dashboard or static site showing flagged divergences, filterable by district/year/subject.

## 7. Future directions (not in v1, worth keeping in view)
- **Best-practice mirror:** instead of only flagging negative divergence, also surface districts getting strong outcomes relative to spending — lower liability, more actionable for school boards.
- **Self-service framing:** let a district's own CFO/board use the tool pre-budget-season to benchmark against similar-size districts.
- **Broader outcome metrics:** chronic absenteeism, graduation rates, CRDC data — richer picture than test scores alone.
- **ESSER-cliff framing:** a time-boxed analysis of which districts' pandemic-relief spending produced measurable, durable gains vs. which didn't, timed to the current funding cliff.

## 8. Suggested tech stack (for Claude Code handoff)
- **Data layer:** Python (pandas) for SACS .mdb parsing and CAASPP file ingestion; SQLite for local storage during Phase 1-2, Postgres if the dataset grows.
- **Join logic:** CDS code as canonical key; build and maintain a CAASPP-ID-to-CDS-code lookup table as its own versioned artifact, since it's the most fragile part of the pipeline.
- **Output:** flat table or lightweight API (district, year, function, spend, ELA%, math%) that a visualization layer can consume.

## 9. Open questions for the team
- Which specific CAASPP metric(s) do we standardize on — proficiency % (met/exceeded), Distance From Standard, or both?
- Do we normalize spending per-pupil, or use raw function totals? (Per-pupil is almost certainly right, but should be an explicit decision, not a default.)
- How many years of history do we pull for Phase 0/1 — enough to see a trend, not so many that CAASPP methodology changes (e.g., pre/post-2015 SBAC transition) confound the comparison?

## 10. Success criteria for the pitch/demo
A single, concrete, correctly-sourced example (e.g., a district's spending-by-function trend plotted against its CAASPP trend, with a visible divergence or convergence) that the team can point to and say "this is what the tool would surface at scale."
