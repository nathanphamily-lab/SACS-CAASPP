# Phase 3 — Dashboard (Presentation Layer)

Scope note: this phase builds the public-facing dashboard on top of the Phase 2 dataset. Do not modify the Phase 1/2 pipeline to support dashboard features. If a view needs data the pipeline doesn't produce, stop and flag it rather than extending the pipeline inside this task.

## Planned views
The dashboard has four views, switchable by tab, sharing one set of global filters (district, year range, subject).

| View | Status |
|---|---|
| District trend | Built |
| Kinds of dollars | Built |
| Method & caveats | **Next** (Task 1) |
| School explorer | **DO NOT BUILD** (see below) |

## DO NOT BUILD: School Explorer

Claude Code proposed a School Explorer view sourced from ESSA data. **Do not build it in this phase, and do not scaffold, stub, or add a placeholder tab for it.**

Why:
- **ESSA school-level financial data cannot show "kinds of dollars."** What it distinguishes is *funding source*, meaning federal vs. state/local money. It does not break spending down by function (instruction, pupil support, administration) the way SACS does, and "kinds of dollars" is exactly what this tool exists to show. A school-level view would be the one place in the dashboard where that capability disappears.
- **It would mix granularities.** The pipeline's spending data is district-level because SACS is district-level. Placing school-level outcomes next to spending that is either district-level or only split by funding source implies a school-level spending analysis the data cannot support.
- **A federal-vs-state split is a different, narrower question** than the one the project is asking (which kinds of dollars yield a sub-par return). It may be worth its own investigation later, but not as a tab on this dashboard.
- **Unverified caveat:** school-level expenditure figures under ESSA reporting may depend on how each district allocates shared central costs to schools. Methods can vary by district. Confirm this against CDE documentation before anyone relies on school-level comparisons.

If the team wants to revisit this, it needs its own spec and task doc, including a decision about whether a federal-vs-state-only view is worth building at all. It does not get added to this phase.

## Task breakdown

### Task 1 — Method & caveats view
Build the tab and write its content. Cover:
- Data sources and years (SACS, CAASPP), and how the two are joined (CDS code).
- What the tool does not claim: not a fraud tool, no ranking, no finding that spending "doesn't work."
- **The funding-formula confound:** California's LCFF directs extra funding to districts with higher shares of high-need students, so higher spending can correlate with lower scores without implying waste. State this plainly.
- How suppressed CAASPP values are handled (shown as "not reported," never as zero).
- Known limits: district-level only, test scores are one contested outcome measure, correlation is not causation.

### Task 2 — Persistent caveat notice
Add a short, always-visible note on every view (not only the Method tab) pointing to the funding-formula confound and linking to the Method & caveats tab. Keep it one or two lines.

### Task 3 — Tabs and shared global filters
Implement tab navigation across the three views being built (District trend, Kinds of dollars, Method & caveats). Filters for district, year range, and subject must persist when switching tabs. Do not give each view its own separate controls for these.

### Task 4 — Guardrail audit of the two existing views
Review District trend and Kinds of dollars against these rules and fix any violations:
- No single "ROI score," composite index, or ranking of districts anywhere.
- Suppressed or missing values render visibly as "not reported," never blank or zero.
- Rows carrying the Phase 2 data-quality flag are visibly marked.
- Per-pupil vs. raw spending is labeled clearly on every chart.

## Explicitly out of scope
- The School Explorer view (see above)
- New data sources of any kind
- Statewide expansion beyond LA County
- A "similar districts" comparison or best-practice view (logged as future directions in the spec doc)
- Automated refresh or scheduled data updates

## Definition of done
The dashboard has three working tabs (District trend, Kinds of dollars, Method & caveats) with shared persistent filters, a visible caveat note on every view, and all Task 4 guardrails passing. No School Explorer code or placeholder exists in the repo.
