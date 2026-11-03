# Keep a branch working offline and reconcile it safely with the cloud

## Title and ID
`washday-mvp-sync` — Role split, replication, mode migration and laptop outage (milestone 5).

## Source
[PRD](../../reference/docs/PRD.md) §3 Sync protocol, Deployment modes, tenant scoping; §4 Event/settings; §§6–8; §9 milestone 5, rollout steps 3–4/checklist lines 543, 547, 550, 553–554; §10 network/setup.

## References
[Package README](../../reference/README.md) mapping of sync pill to server outbox; [preview](../../reference/prototype/index.html) staff/owner board and machine presentation only (offline toggle/localStorage not functional authority); [logo](../../reference/img/logo-header.png), [paper sheet](../../reference/docs/paper-job-sheet.pdf) for hub failure fallback; [shared constraints](README.md#shared-execution-constraints).

## Desired outcome
A laptop hub serves its own branch independently of internet, synchronises complete ordered/idempotent operational history to the cloud, receives shop settings and permits lossless switching between direct and hub service.

## Dependencies
`washday-mvp-direct-pilot`: direct + simple pilot evidence meets the rollout gate. All earlier staff/owner functionality must regress in both roles. External: cloud test endpoint, router internet-disconnect access, laptop configured not to sleep/firewall open, JR's phone plus another shared device.

## Acceptance criteria
- **AC-01:** One codebase/image runs `APP_ROLE=hub` (SQLite WAL, only assigned branch) or cloud (PostgreSQL, owner + direct branches). Cloud refuses staff routes for hub branches; hub serves only its branch. State+immutable UUID/branch-seq Event remains atomic in either mode, and direct writes need no outbox.
- **AC-02:** Hub outbox sends unsent batches of **up to 500 every 30 seconds** online, exponential backoff on failures; cloud authenticates only enrolled hashed hub keys and accepts only their shop/branch. Duplicate UUIDs are idempotent and replay/out-of-order batches produce no lost/duplicated state, collections, stock or events. Acknowledgement/highest-sequence handling never marks a missing event as sent; prove recovery from gaps and dropped responses.
- **AC-03:** Hub pulls shop settings/catalog on startup and **every 5 minutes** using settings version, applies changes atomically and never receives another shop's catalog. Operations flow up only, shared settings/catalog down only. Staff on hub see “Connected” when reaching the hub, never cloud status.
- **AC-04:** The only upward catalog exception is an unlocked staff-added SupplyType with UUID. Two branches adding the same name offline retain both cloud records and present an owner merge-required decision, rather than dropping a type/history or crashing sync. Normal non-conflict case-insensitive uniqueness/restoration rules still apply. Per approved D-03, owner chooses the surviving type and its settings; reconcile references and balances while preserving both histories and all immutable Events, without losing or double counting stock. Subsequent settings pulls converge hubs on that resolved identity/settings; replay of old events referring to either original UUID remains safe.
- **AC-05:** Bootstrap provides only that branch's current state and synced events plus its shop settings/catalog. Direct → hub: prepare/bootstrap, switch after closing, stop cloud staff service, re-enrol at hub address. Hub → direct requires pushing all unsent events and an empty outbox before switch/re-enrol. Round trip loses/duplicates no event or record and cannot keep two active writers through the switch.
- **AC-06:** Same pytest/Cypress staff flow suites pass in hub/direct roles, including pricing, stale actions, stocks, devices/PINs, Undo, paper, default/custom stage rules, history and tenant isolation. Image builds and tests pass on **amd64 and arm64**, including laptop arm64 when Apple Silicon. Prior owner/report acceptance is rerun against replicated events.
- **AC-07:** With internet disconnected **at the router/modem, not laptop Wi-Fi**, run **4 hours offline under load** on laptop hub with personal + shared devices; every device keeps working/stays in step, staff see no visible internet-loss effect, and reconnect synchronises with zero lost/duplicated events. Offline storage supports **at least 30 days of unsent events**, separately tested for capacity/retention rather than inferred from four hours.
- **AC-08:** Hub pages respond **under 200 ms on local Wi-Fi**, actions complete **under 300 ms**; when online, owner sees branch events **within 1 minute**. Owner displays stale/as-of view, >30-minute hub alert and correct post-reconnect totals. Locally served fonts/icons/logo and all staff screens remain usable with internet cut.
- **AC-09:** Home dry run on laptop covers **a full day of sample jobs**, JR's personal phone and a second shared device, including internet cut and rejoin. Both stay in step; sample data remains development-only and is kept out of production.

## Constraints
[Shared constraints](README.md#shared-execution-constraints); DRF only for sync endpoints `/sync/push/`, `/sync/pull/`, `/sync/bootstrap/`. No browser-side sync database/service worker. Retain all original timestamps, actors and event IDs; don't renumber replicated jobs. Laptop testing cannot establish N100 power recovery, UPS runtime or unattended Ubuntu/Tailscale operation.

## Out of scope
Nightly update/backups/spare recovery and Tailscale operational integration: `washday-mvp-hub-operations`; real seven-day N100/UPS check: `washday-mvp-hardware`; live hub pilot/remaining branches: `washday-mvp-hub-rollout`.

## Verification notes
Use three test branches plus second shop and foreign hub key; replay batches, reorder sequences, inject gaps/duplicate responses, backoff/restart, interrupted bootstrap/settings apply and mode switch. Reconcile UUID/sequence sets, projections, stock and money before/after. Required pytest sync/tenant suites, Cypress both roles, multiarch test logs, measured latency, four-hour outage log and full-day home dry run are separate evidence. Thirty-day retention may use a documented representative capacity fixture; no requirement to wait thirty days is invented.

## Open questions/blockers
Blocked by direct-pilot gate and external laptop/router/cloud/devices access. D-03 resolves owner survivor/settings selection for offline duplicate supply types. Multi/no-stage category mapping draft from machines/settings affects AC-06; it must not be silently “resolved” by fixtures that avoid those configurations.
