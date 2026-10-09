# Project Status — CA School Spending vs. Outcomes

Source of truth for where things stand. Each doc below owns its own scope — this file just tracks state and links out; it doesn't duplicate their content.

## Docs
- [`maia_spending_outcomes_spec.md`](./maia_spending_outcomes_spec.md) — the why/what, for the team
- [`README.md`](./README.md) — general build orientation, data sources, repo structure
- [`PHASE1_TASKS.md`](./PHASE1_TASKS.md) — single-district (LAUSD) pipeline
- [`PHASE2_TASKS.md`](./PHASE2_TASKS.md) — scale to all LA County districts (79 per CDE and SACS)
- [`PHASE3_TASKS.md`](./PHASE3_TASKS.md) — dashboard (presentation layer)

## Phase status

| Phase | Status | Summary |
|---|---|---|
| Phase 0 (manual proof) | Done | LAUSD numbers manually pulled and confirmed divergence pattern is real |
| Phase 1 (single-district pipeline) | **Done** | LAUSD pipeline built and verified against hand-pulled ground truth |
| Phase 2 (79-district pipeline) | **Completed** | All 79 LA County districts (CDE/SACS count, not 80), 2022-23 → 2024-25, one flagged dataset; 4 districts verified vs their filings — see `notes/phase2_signoff.md` |
| Phase 3 (presentation layer) | **Done** | `docs/index.html`: 3 tabs (District trend, Kinds of dollars, Method & caveats), shared district/year/subject filters, LCFF caveat on every view, Task 4 guardrails; all 79 districts |
| Future directions (best-practice mirror, self-service, CRDC, ESSER-cliff framing) | Not started | Logged in spec doc section 7 as ideas, not committed scope |

*(Update the table above as things move — keep it to one line per phase, don't let status notes grow into a changelog.)*
