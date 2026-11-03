# Move and release individual jobs without losing payment or paper times

## Title and ID
`washday-mvp-progression` — Board, simple mode, corrections and claim (milestone 1).

## Source
[PRD](../../reference/docs/PRD.md) §§3–5 staff routes/screens; §6 Job stages, Simple mode, Paper job sheet; §7; §8; §9 milestone 1, checklist lines 515, 521–522, 527–529, 542.

## References
[Preview](../../reference/prototype/index.html): Staff → Jobs board, `ordersView`, `orderCard`, `editStage`, `claim`, `visibleStageIds`, `shownIn`; presentation authority only. [Paper sheet](../../reference/docs/paper-job-sheet.pdf): Ready tick and Part B release reconciliation. [Package authority](../../reference/README.md), [brand](../../reference/img/logo-header.png), [shared constraints](README.md#shared-execution-constraints).

## Desired outcome
Staff can move each job independently to Ready and release it with accurate payment, correct an incorrect stage, and reconcile paper releases. Simple mode shortens the visible flow without rewriting job state.

## Dependencies
`washday-mvp-intake`: persisted, scoped jobs, pricing snapshots, events, paper intake and reusable visual shell must pass their criteria.

## Acceptance criteria
- **AC-01:** Default stages are Received → Washing → Drying → Folding → Ready, then Claimed. Every active board card shows its job number, customer, size/service, age, paid state, overdue flag and its own Next or Claim button; moving one does not move its neighbors. The board refreshes with HTMX every 20 seconds.
- **AC-02:** In full mode the board button targets exactly the next active stage; machine-demanding transitions have the integration contract owned by `washday-mvp-machines`. A simple-mode branch instead shows first/last and only middle stages ticked Show in simple mode (default off), and advances to the next shown stage without a picker or skip reason. New branches default to direct + simple.
- **AC-03:** Simple mode hides Machines navigation/screen and restricts manual override choices to shown stages. A job in a hidden stage appears in the nearest earlier shown column labelled with its actual stage; advancing reaches the next shown stage. Returning to full mode preserves every actual stage. Intake, list/history, supplies, payment and PIN policies stay applicable.
- **AC-04:** Manual correction can set any stage from first through Ready, forward or back, with an optional reason. It records `stage_overridden` with from/to/reason/actor; timeline evidence is “Stage changed to X, manual override from Y”. It never claims a job, opens a machine picker or ends an open load. Packing supplies are deducted only at the first Ready arrival and never returned merely by moving backward (ledger integration: `washday-mvp-supplies`).
- **AC-05:** Every job action carries its expected current stage; if another device already changed it, the server refuses the mutation, states the actual stage (for example “Job #1043 is already in Drying”), and refreshes the page. No payment, stock, load or event side effect occurs from the stale action.
- **AC-06:** Claim from Ready records Cash/GCash and optional GCash reference when unpaid, sets payment and claim times, marks Claimed and writes `job_claimed` atomically. Already-paid jobs retain the original payment and are not collected twice. Repeated/stale claims cannot create a second collection or release.
- **AC-07:** Released on paper captures the sheet's time out, and any payment time as written, rather than entry time; the same today-to-7-days-back/no-future sheet-date rule applies. A paper job can reach Ready without a load or picker even at a full-mode branch; packing/add-on deductions still apply, washer deductions do not. Paper release for an existing app job is supported by its app number as well as reconciliation of P-number jobs.
- **AC-08:** Claim stub reflects the resulting paid/released state, board excludes Claimed jobs and displays today's claimed count using Asia/Manila and actual `claimed_at`. All mutations preserve transactional append-only events and tenant/branch isolation. Corrections and releases show toasts and prepare reversible-action feedback for `washday-mvp-people`.
- **AC-09:** Board, correction and claim views meet shared visual, touch, theme, locale and accessibility constraints at 390/1280 px and 360 px. Only the board's own container scrolls horizontally. Ready-overdue behavior measures time actually in Ready, not the preview's creation-time shortcut; owner alert threshold is owned by `washday-mvp-monitoring`.

## Constraints
[Shared constraints](README.md#shared-execution-constraints) apply. Server rules override prototype localStorage, blanket PIN prompts and in-memory undo. PIN enforcement and six-second compensating Undo belong to `washday-mvp-people` before production. Model the default stage settings now; owner editing is milestone 4. Full-mode machine-dependent success is not accepted until `washday-mvp-machines` integrates it; milestone 1 is verifiable through simple mode and explicit machine-skip paths with required reasons.

## Out of scope
Machine picker/load execution: `washday-mvp-machines`; stock changes: `washday-mvp-supplies`; staff/PIN/Undo: `washday-mvp-people`; stage editor: `washday-mvp-settings`; list/history presentation: `washday-mvp-history`.

## Verification notes
Use simultaneous device sessions, multiple cards in one column, pre-paid/unpaid Cash/GCash jobs, paper intake and paper release on a different entry date, and hidden-stage fixtures. Run pytest transitions, stale-action refusal and duplicate payment checks. Assert Events and snapshots as well as DOM results. Verify correction leaves an open fixture load unchanged and Ready is reached without loads for paper/simple mode; rerun with the actual machine/stock integrations later. No unimplemented dependency contract counts as a passed integration check.

## Open questions/blockers
Blocked by `washday-mvp-intake` evidence. No unresolved functional decision.
