# Give the owner accurate totals, alerts and a watch-only branch view

## Title and ID
`washday-mvp-monitoring` — Dashboard and Live branches (milestone 4).

## Source
[PRD](../../reference/docs/PRD.md) §§3–5 dashboard/live routes/screens; §6 Owner alerts, Totals on the dashboard, Supplies count status, Simple mode; §§7–8; §9 checklist lines 523, 531, 533–534, 544. D-01 [opening time](README.md#owner-clarifications).

## References
[Preview](../../reference/prototype/index.html): Owner → Dashboard / Live branches, `dashView`, `liveView`, `countHistory`, `countStatus`. PRD overrides its creation-time shortcuts, alert duplication and simulation. [Brand](../../reference/img/logo-header.png), [package README](../../reference/README.md), [shared constraints](README.md#shared-execution-constraints).

## Desired outcome
The owner can reconcile today's business, identify concrete branch problems and watch staff state without being able to perform branch operations through the live view.

## Dependencies
`washday-mvp-settings`: authorised, scoped owner session; all staff records, settings and branch hours are available.

## Acceptance criteria
- **AC-01:** Dashboard filters all/one shop branch and shows sales total/Cash/GCash (`paid_at` today jobs + self-service loads started today), loads started today, kilos from `received_at` today, Ready/unclaimed count and unpaid amount still to collect. Manila midnight is the boundary; paper encoding day is irrelevant to these totals.
- **AC-02:** Loads-per-machine uses recorded loads grouped per selected branch/category, omits simple-mode branches, and explains the empty all-simple state. Branch tablets marks Simple; Live branches hides simple branch machines/machine counts and shows “Simple mode”.
- **AC-03:** Needs attention lists low stock at `on_hand <= low_level`; count nonzero variances from counts saved today/yesterday (latest count if none then), one alert per supply; Ready **more than 2 days** with unpaid note; open supply requests. Ready age uses actual Ready arrival, not receipt age.
- **AC-04:** Latest full count controls branch freshness by Manila calendar day: today/yesterday green, 2 days ago orange, ≥3 days or never red. Partial counts never refresh that status. Tapping shows history with time/actor/full-or-partial and each supply's expected → counted/variance, including archived supply history.
- **AC-05:** Owner can turn an open SupplyRequest into a supply type using the settings validation/restore rules and retain its resolved state; open requests remain actionable in dashboard. No duplicate/foreign-shop type can be injected by a request.
- **AC-06:** Branch tablets distinguishes Direct with device-last-seen from hub last sync. Hub unsynced **more than 30 minutes** alerts; direct branch devices unseen **more than 30 minutes during opening hours** alerts “may be on paper”. Opening window uses owner-approved opening_time + closing_time; actual real branch times are loaded before pilot. Hub-specific live evidence is completed under sync.
- **AC-07:** Live branches selects one shop branch, displays counts, machine grid and board, refreshes every **20 seconds**, and shows offline/as-of evidence rather than falsely current data. It reuses `jobs/_card.html` and `machines/_tile.html` with `read_only=True`; no branch action controls or owner bypass of staff mutation routes are exposed.
- **AC-08:** Online branch events become visible to the owner within **1 minute**. Dashboard loads in **under 2 seconds on mobile data**. Record direct-mode measurements here and reverify hub delivery under sync, including stale/as-of behavior after an outage.
- **AC-09:** Cross-shop owner session/filters/URLs cannot reveal totals, requests, counts, branches or events and return 404 for foreign records. Shared theme, 390/1280 px prototype comparison, 360 px, text status, keyboard focus, touch and local-brand asset constraints pass on these screens.

## Constraints
[Shared constraints](README.md#shared-execution-constraints); owner is cloud-only. No owner branch-operation mutation through Live branches. Use operational timestamps and compensation-aware totals; later sync cannot reuse a stale pre-sync PASS. Do not imitate preview sample data, simulated offline toggle or browser-local totals.

## Out of scope
Underlying staff work: previous owners; BIR/privacy export: `washday-mvp-reports`; physical network/device evidence: cloud release and sync; pilot metrics: direct pilot / hub rollout.

## Verification notes
Clocked fixtures around Manila midnight and thresholds (2 days Ready, 30 min unseen, 0/1/2/3 full-count days) with recent partial counts, nonzero signed variances, duplicate alerts, paper next-day entries, self-service and compensation. Reconcile totals to events/ledger independently, test request conversion, owner isolation and read-only routes. Capture real mobile-data timing and one-minute visibility; do not infer them from local server timings.

## Open questions/blockers
Blocked by `washday-mvp-settings` evidence. Source does not specify irregular/overnight opening schedules; D-01 provides ordinary branch opening/closing times. If real branch hours cross midnight or vary by day, resolve that schedule before AC-06's production verification rather than inventing it. Hub delivery evidence remains prerequisite work in sync, not assumed complete here.
