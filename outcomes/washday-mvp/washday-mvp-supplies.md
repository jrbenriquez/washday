# Keep branch supplies accurate through use, receipts and counts

## Title and ID
`washday-mvp-supplies` — Supply ledger and staff requests (milestone 2 completion).

## Source
[PRD](../../reference/docs/PRD.md) §§3–5 supply models/routes/screens; §6 Supplies, Simple mode, Paper job sheet; §§7–8; §9 milestone 2/checklist lines 527, 532, 534–535.

## References
[Preview](../../reference/prototype/index.html): Supplies, Receive, full/partial count, new-supply request/type; `suppliesView`, `transfer`, `saveCount`, `supplyForm`, `varHTML`; presentation only. [Paper sheet](../../reference/docs/paper-job-sheet.pdf) has no stock section. [Brand](../../reference/img/logo-header.png), [package authority](../../reference/README.md), [shared constraints](README.md#shared-execution-constraints).

## Desired outcome
Staff see auditable branch stock, automatic usage from normal work, receipts and counts, and can request supplies without bypassing the owner's supply-type permission.

## Dependencies
`washday-mvp-machines`: load/stage events and deduction integration points exist; counter/history criteria pass for the default configuration.

## Acceptance criteria
- **AC-01:** On hand is the sum of signed StockEntry quantities per branch/type; Supplies shows active types, units, on hand, used today and Low when `on_hand <= low_level`. No independent mutable balance may diverge from the ledger.
- **AC-02:** Job creation deducts configured AddOnUse amounts; category load start deducts every active supply's per-washer-load amount when the category uses wash supplies; first-ever Ready arrival deducts per-packed-job amounts. Each operation writes stock/state/events atomically with correct job/load/reason links. Repeated requests, stale actions and backwards stage corrections do not double deduct.
- **AC-03:** Archived types are excluded from staff choices and all automatic deductions, including add-on recipes, but remain in earlier ledger/count/report evidence. Simple/paper jobs have no washer-load deductions; add-on and first Ready packing deductions still happen.
- **AC-04:** Receive accepts a positive amount and appends a receipt; invalid amounts do not mutate stock. Recent changes are newest first, **10 per page**, Newer/Older, showing reason, supply, signed amount, time and linked job number when applicable; tapping opens the job timeline.
- **AC-05:** A count may be saved at any time. Full covers every active type; partial covers only entered lines and leaves the rest untouched. Each line snapshots expected/count/variance (`counted − expected`); each nonzero variance creates `count_adjust` so stock equals the count. Zero variance does not create an adjustment. Counts/lines are never edited/deleted.
- **AC-06:** Variance magnitude 1–3 displays warning; more than 3 critical, with sign/text as well as colour. Owner count freshness/history presentation is owned by monitoring; stock data retains timestamp, actor, full/partial and expected → counted for that view.
- **AC-07:** With staff adding locked, the new-type route refuses attempts and staff can send SupplyRequest(name, optional note, actor, branch, open status). When unlocked, staff can add a type with unit, threshold and usage amounts. Names are case-insensitively unique within the shop; an archived name requires restoring the original, not adding another. Owner add/restore/request resolution is `washday-mvp-settings` / monitoring.
- **AC-08:** All stock mutations and reads enforce shop/branch isolation and append immutable Events, including count/request actions discoverable in History. Race checks preserve a correct ledger/count snapshot. Shared-device PIN and Undo policies integrate under people without editing/deleting immutable counts.
- **AC-09:** Required stock-ledger pytest checks and Cypress count flow pass, including partial count. Supply screens match the referenced layout at 390/1280 px light/dark and 360 px, with shared accessibility/local assets and no page overflow.

## Constraints
[Shared constraints](README.md#shared-execution-constraints); catalog SupplyType is shop-owned, stock is branch-owned. Initial production amounts are supplied by the owner; sample recipes are fixtures only. Do not build central purchasing/transfers as a new subsystem: Receive is the specified positive branch entry. Offline duplicate-name reconciliation is a required exception owned by sync, not permission to weaken normal uniqueness.

## Out of scope
Owner supply settings: `washday-mvp-settings`; request dashboard, variance alerts and freshness/history: `washday-mvp-monitoring`; offline cross-branch name conflicts: `washday-mvp-sync`; PIN/Undo: `washday-mvp-people`.

## Verification notes
Use recipe changes, archived type references, wash and non-wash categories, repeated Ready visits, a full count and spot checks, zero/±1/±3/±4 variance, pagination beyond 10, duplicate active/archived names and a second shop. Reconcile sum of entries to every displayed balance. Run pytest ledger/tenancy and Cypress count, then regress intake/machine/paper flows with real ledger effects. Owner-view acceptance is verified in its owning outcome.

## Open questions/blockers
Blocked by `washday-mvp-machines` evidence; its custom-mapping draft must be resolved for complete milestone 2 acceptance. No additional missing decision.
