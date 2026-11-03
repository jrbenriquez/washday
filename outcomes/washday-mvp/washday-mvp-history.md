# Find jobs and reconstruct the branch's day from events

## Title and ID
`washday-mvp-history` — Jobs List, History and timeline (milestone 1 completion).

## Source
[PRD](../../reference/docs/PRD.md) §3 Jobs routes; §4 Event/Job/JobLine; §5 Jobs; §6 Job list and history, Paper job sheet; §§7–8; §9 checklist lines 512–513, 542.

## References
[Preview](../../reference/prototype/index.html): Jobs → List / History → job detail; `jobsToolbar`, `jobListRows`, `historyRows`, `showJobDetail`. Presentation only; its derived browser arrays are not the required event read model. [Paper sheet](../../reference/docs/paper-job-sheet.pdf), [package README](../../reference/README.md), [logo](../../reference/img/logo-header.png), [shared constraints](README.md#shared-execution-constraints).

## Desired outcome
Staff can find current or released jobs, audit receiving through release, and reconcile each day's jobs and collections—including paper jobs entered later—without seeing another branch's history.

## Dependencies
`washday-mvp-progression`: actual intake, payment, stage and claim events, including paper occurrence times, are available and verified.

## Acceptance criteria
- **AC-01:** Jobs switches among Board, List and History. Date defaults to today in Asia/Manila; Today, Yesterday and a date picker select the day. Search spans all dates and matches job number, P number, customer name/phone, notes, status and payment method, with clear all-dates/empty-result feedback.
- **AC-02:** List includes every branch job received, paid or released on the chosen day, including already released jobs, newest first. Rows show number, customer, kg/pieces, service, state, received/released times, amount/method/time paid or Unpaid and amount due; paper jobs carry a Paper badge.
- **AC-03:** List and History open the selected job's timeline. It shows ordered Received (size/service/total/actor), stage changes and reasons, Paid (amount/method/reference/actor, “at drop-off” when applicable), and Released with actor; price lines and a stub link remain available. Machine load/unload durations and automatic machine-caused stages appear once `washday-mvp-machines` is integrated.
- **AC-04:** History is newest-first branch Events for the day, not only events belonging to active jobs. Day summary counts jobs received/released and money collected total/Cash/GCash exactly once. Self-service collections and stock/device action events are included as those behaviors arrive; no fake job is created for self-service.
- **AC-05:** Paper received/payment/claim events appear on their sheet days, not entry day. P number is searchable and timeline/stub display “Received on paper as P-7, entered by [Staff] at [time]” with actual values. Entry provenance and occurrence time remain distinguishable.
- **AC-06:** Both views are built from the append-only Event log, scoped to the enrolled branch/shop; same-number jobs in another branch cannot leak. Foreign-shop identifiers return 404. Compensating events later added by `washday-mvp-people` remain visible and summaries reflect the resulting corrected collections rather than double counting.
- **AC-07:** List/history/timeline satisfy shared themes, 390/1280 px reference presentation, 360 px support, textual status, labelled controls, visible focus, touch targets and no page-level horizontal overflow.

## Constraints
[Shared constraints](README.md#shared-execution-constraints); use server-side Event reads rather than the prototype's generated `o.log` or browser timezone. Preserve line snapshots even after catalog archiving. Add regression fixtures when later slices introduce new event types; historical PASS here does not establish coverage of those future events.

## Out of scope
Creating/changing jobs: intake/progression owners; load generation: `washday-mvp-machines`; owner totals/export: `washday-mvp-monitoring` / `washday-mvp-reports`.

## Verification notes
Use dates around Manila midnight, a job received/paid/released on different days, next-day paper encoding, same numbers/P numbers at other branches, all search fields and no matches. Compare summaries to expected Event fixtures; run pytest on date/search/projection isolation and paper-time regressions. Extend fixtures and rerun after machines, supplies and Undo. UI screenshots at required sizes/themes are evidence, not a substitute for event reconciliation.

## Open questions/blockers
Blocked by `washday-mvp-progression` evidence. None otherwise.
