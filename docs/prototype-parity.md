# Prototype parity: 4 November 2026

Compared against `reference/prototype/index.html`, starting from main `7e06b91`. The [route map](prototype-route-map.md) records the current destinations and differences by prototype ID.

## Implemented

- Owner Dashboard: branch filters, actual collection/load/received/Ready KPIs, category-coloured machine-load bars, low-stock/count/overdue/request alerts, stock-count recency/history, device last contact, and a working date/branch-filtered Excel collections report.
- Owner Live branches: branch selector, simple/full modes, running/check/in-progress/Ready KPIs, read-only machine portholes and job boards, server timestamp, and 20-second refresh.
- Owner Staff: branch filters, avatar/access/shift cards, creation, PIN reset, activation, deactivation and branch transfer. Transfers require a fresh PIN unique in the destination branch and end personal shifts.
- Owner Machines: categories plus branch cards, creation/editing, out-of-service status, archive/restore. Active loads prevent removal or branch/category/service-state changes.
- Owner Settings: minimum kilos, kilos/load, check threshold, staff supply permission, branch simple mode, PIN actions, theme, branding, stage ordering/machine/auto-next/simple settings, services, fees, add-ons, supply recipes, supplies, pieces and sizes. Inserting/restoring stages keeps a distinct order with first/Ready endpoints. Existing job price lines and historical ledgers remain unchanged.
- Shared shell: prototype segmented owner tabs, contextual Manila clock, theme controls, Ready/check badges and browser connectivity indication.
- Staff intake: next-number tags, customer identity/reset, per-load hint and create-button state. Native inputs and server pricing remain authoritative.
- Jobs: stage chips, payment/status/price/notes hierarchy, event-kind timeline colours, and dialogs for stage correction, claim, stub and history.
- Supplies: stock table beside ledger, receive/request sections, full-width count table with live variance, count history and severity badges. Machines gain the daily-load summary and state legend.
- Dialogs: native dialog overlay, close/Escape/focus restoration, actual server POST destinations, direct-route fallback and print handling. Owner catalog links open the same form as either a dialog or a standalone page.

## Preserved decisions and remaining differences

Authentication still separates owners from enrolled branch devices. There is no unauthenticated role switch or arbitrary staff branch selector. Machine starts remain driven by the Jobs board, as recorded in the [accepted decision](../outcomes/washday-mvp/decisions/2026-11-03-machine-start.md).

The prototype's offline switch and sample-data reset are simulations. Hub replication, durable server-side queues and compensating Undo are now implemented; see [the operator guide](offline-and-undo.md). Direct device last contact remains labelled as contact history; authenticated hub sync is displayed separately. The Excel export contains daily collections, including self-service, and does not claim to implement a prescribed BIR template that was not supplied.

Machine pickers, device enrolment and one-time PIN/code display retain their existing secure page flows. PIN entry now opens over the originating screen, using the existing action-bound server guard. Machine unload remains an explicit button. Staff receipt/request forms remain visible sections; catalog creation uses dialogs; settings catalog fields now save inline with explicit Save buttons as a fallback. Stock-count history uses a paginated owner page. Customer creation retains the existing name/phone fields alongside search/selection/reset. Add-on recipes appear as supply chips with quantity editing and removal; piece sizes are grouped within a single Piece items card. Reversible-action toasts now offer a six-second, device-bound Undo.

## Verification

- `uv run pytest -q`: **106 passed, 1 skipped**. The existing concurrency test skips on in-memory SQLite; its file-backed probe is `scripts/check_concurrency.py`. New owner tests cover actual collections, tenant isolation, CSRF, archive/restore, immutable job prices, operational validation, active loads, stage insertion/restoration, request fulfilment and branch-unique PIN transfers.
- `uv run python manage.py check`, `uv run python manage.py makemigrations --check --dry-run`, `node --check static/js/app.js`, and `git diff --check` pass. No schema migration is required.
- `uv run python scripts/check_prototype_parity.py`: isolated temporary database and private fixture owner session; no public owner-authentication bypass. Captures 15 pages at 360/390/1280 pixels in light/dark themes, plus reference-owner and stage-dialog screenshots. Browser checks cover no page overflow, loaded routes/themes, owner creation/archive/restore, modal Escape/focus/POST routing, stage correction/claim/payment, Excel download, theme persistence, live read-only controls, intake create state and stock-count variance. Fixtures include a running machine above the check threshold, a Ready job, count variance and an open supply request.

Evidence: [browser results](../.agents/work/prototype-parity/evidence/current/browser.json), [owner dashboard](../.agents/work/prototype-parity/evidence/current/dashboard-1280-light.png), [phone machine administration](../.agents/work/prototype-parity/evidence/current/machine-admin-390-dark.png), [phone stage dialog](../.agents/work/prototype-parity/evidence/current/stage-dialog-390.png). Captures use equivalent viewports, fonts and themes; operating data intentionally differs from the prototype's hard-coded sample shop.


## Owner settings catalog follow-up

Services, fees, add-ons and supply types use prototype-specific columns, inline validated edits, and compact removed/archived lists. Supply permissions live in Supply types. Add-ons contain their own supply recipes, and Piece items groups each item's sizes and supports adding the first price atomically, adding/removing/restoring sizes, and archiving/restoring an item. Jobs retain their saved prices and stock deductions use the same tenant-scoped catalog records.

Run `uv run python scripts/check_owner_settings_browser.py` with a fresh `EVIDENCE_RUN` to check actual browser saves, grouped size creation/removal/restoration, recipe chips, supply permissions, archive/restore, desktop/tablet/phone layouts in both themes, and Save without JavaScript. This probe uses a temporary database and private fixture owner session.


## Claim, payment and PIN follow-up: 6 November 2026

Claim/payment and shared-device PIN confirmation stay in a native dialog over the originating screen. Cash/GCash use prototype-style segmented controls; the reference field appears only for GCash. The PIN keypad supports touch and keyboard entry, clears/deletes digits, submits at four digits, and displays server validation failures in the dialog. Cancel/Escape save nothing. Successful claims refresh the board without changing its URL or filters, and keep feedback and Undo. Intake PIN approval opens the stub over a reset intake screen. Forms remain usable without JavaScript, with the same server-side authorization and CSRF checks.

Paper-release dates and times are hidden until Released on paper is checked, and posted values survive validation errors. The layout pass aligns modal padding, amount sizing, card spacing, intake header actions, payment segments and summary hierarchy with the prototype. Authentication and branch-specific operating data remain authoritative.

Verification: `uv run pytest tests -q` (169 passed, 1 skipped), Django system/migration checks, JavaScript syntax and diff checks. `EVIDENCE_RUN=claim-modal uv run python scripts/check_prototype_parity.py` captures 15 screens at 360/390/1280 pixels in both themes and tests actual enrolled-device PIN, cancellation, invalid PIN retry, paid/unpaid claims, persisted GCash references and intake approval. `INTERACTIONS_ONLY=1` skips the full-screen capture matrix for focused reruns.
