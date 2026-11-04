# Prototype → current app page map

Source: [`reference/prototype/index.html`](../reference/prototype/index.html). Mapping updated: **4 November 2026**. Browser evidence and remaining differences: [`prototype-parity.md`](prototype-parity.md).

The prototype is one HTML page: its tabs and dialogs do not have separate URLs. The tables below map those UI locations to **existing current-app routes/pages**, including sections embedded within a page. An existing equivalent means the feature has a UI destination; it does **not** mean its design or layout matches the prototype.

This is a source-based mapping, not a browser visual-parity verdict. Prototype function names are stable search anchors; all implementation paths are relative to the repository root. Route definitions are in [`config/urls.py`](../config/urls.py) and [`owner/urls.py`](../owner/urls.py).

## Reading the map

- **Page** — an equivalent routable page exists.
- **Section** — an equivalent is embedded in an existing page.
- **Partial** — only part of the prototype screen/section has an equivalent.
- **Missing** — no equivalent user-facing page/section exists.
- **Amended** — an accepted change supersedes the prototype interaction.
- **Prototype-only** — a demo/simulation control, not a live-app page.

`{number}` means a job number; `{machine_id}`, `{staff_id}`, `{device_id}` and `{branch_id}` mean UUIDs. Paths identified as **POST** are action endpoints, not pages to open directly.

## 1. Top-level pages

| ID | Prototype navigation / page | Source anchor | Current equivalent route / page | Mapping | Implementation |
|---|---|---|---|---|---|
| P-01 | Staff tablet → New job | `counterView()` | `/jobs/new/` | Page | `templates/jobs/new.html` |
| P-02 | Staff tablet → Jobs → Board | `ordersView()` | `/jobs/` | Page | `templates/jobs/board.html` |
| P-03 | Staff tablet → Jobs → List | `jobListRows()` | `/jobs/?view=list` | Page | `templates/jobs/list.html` |
| P-04 | Staff tablet → Jobs → History | `historyRows()` | `/jobs/?view=history` | Page | `templates/jobs/list.html` |
| P-05 | Staff tablet → Machines | `machinesView()` | `/machines/` (full-mode branches) | Page; amended start flow | `templates/machines/grid.html` |
| P-06 | Staff tablet → Supplies | `suppliesView()` | `/supplies/` | Page | `templates/supplies/index.html` |
| P-07 | Owner → Dashboard | `dashView()` | `/owner/dashboard/` | Page | `templates/owner/dashboard.html` |
| P-08 | Owner → Live branches | `liveView()` | `/owner/live/?branch={branch_id}` | Page; read-only and refreshed every 20 seconds | `templates/owner/live.html` |
| P-09 | Owner → Staff | `staffView()` | `/owner/staff/` | Page; branch filters, shift cards, access editor | `templates/owner/staff.html` |
| P-10 | Owner → Machines | `machinesAdmin()` | `/owner/machines/` | Page; categories and branch machine cards | `templates/owner/machines.html` |
| P-11 | Owner → Settings | `settingsView()` | `/owner/settings/` | Page; operations, branches, display, PIN policy and catalog editors | `templates/owner/settings.html` |

## 2. Shared shell and navigation

| ID | Prototype section | Source anchor | Current equivalent | Mapping / observable source difference |
|---|---|---|---|---|
| S-01 | Shop logo and big blue shop name | `renderTop()` | All staff pages and owner pages: `templates/brand.html`, included by `base.html` / `auth_base.html` | Section. User-approved amendment: signed-out screens show WashDay/generic icon; contextual shops use their own name/logo. |
| S-02 | Current date and time below brand | `renderTop()` | `templates/brand.html` → local Asia/Manila clock, alongside branch context | Section. |
| S-03 | Staff tablet / Owner segmented switch | `renderTop()` | `/` offers entry to owner login or staff setup; owner and staff have separate authenticated flows | Amended for authentication. No equivalent in-shell segmented switch. |
| S-04 | Branch selector | `renderTop()` (`#branch`) | Staff scope comes from the enrolled device; owner administration uses branch-specific forms | No equivalent global selector. |
| S-05 | Simple-mode indicator | `renderTop()`, `ordersView()` | `/jobs/` header | Section; located on board rather than global top bar. |
| S-06 | Moon/sun theme button | `renderTop()` | Staff `base.html` → POST `/theme/` | Section. Staff and authenticated owner shells have a theme control; owner Settings has a display switch. |
| S-07 | Online / synced / offline / pending events pill | `renderTop()`, `scheduleSync()` | Staff header serving hub/cloud connectivity pill | Implemented. Hub staff see connection to their local server; owner sees replication separately. |
| S-08 | Icon rail, active tab, Ready/check badges | `staffShell()` | Staff `base.html` rail | Section. SVG links, active state, Ready count and machine-check badges. |
| S-09 | Owner Dashboard / Live branches / Staff / Machines / Settings tabs | `ownerView()` | Owner segmented navigation: Dashboard / Live branches / Staff / Machines / Settings / Access and devices | Section; authenticated owner entry is preserved. |
| S-10 | Phone bottom navigation / tablet left rail | CSS `.rail`, mobile media query | Shared `static/css/app.css`, staff `base.html` | Section; visual comparison still required. |
| S-11 | Saira Condensed headings, Figtree body, JetBrains Mono numbers; themes/cards/tags | CSS tokens and component rules | `static/css/fonts.css`, `tokens.css`, `app.css` | Shared components exist; this is not proof every page uses equivalent markup. |

## 3. New job / counter sections

All sections below belong to `/jobs/new/` unless another route is listed.

| ID | Prototype section | Source anchor | Current route / section | Mapping / difference |
|---|---|---|---|---|
| N-01 | Screen title, helper text, next-job-number tag | `counterView()` | `templates/jobs/new.html` screen header | Section. Title/helper and estimated next-number tag; From paper sheet remains available. |
| N-02 | Service selection chips | `counterView()` | Service section | Section. Native radios styled as chips. |
| N-03 | Clothes-only weight, minimum hint, per-load hint | `counterView()` | Weight section | Section. Minimum hint and dynamic per-load count/kilos-per-load hint. |
| N-04 | Large kg display and numeric keypad | `counterView()`, `refreshCounter()` | `#kg`, `.keypad`; `static/js/app.js` | Section. Current kg value is directly editable. |
| N-05 | Piece items / sizes / quantity steppers | `counterView()` | Pieces section | Section. |
| N-06 | Add-on chips | `counterView()` | Add-ons within Pieces card | Section. |
| N-07 | Fee chips, including Rush | `counterView()` | Fees within Pieces card | Section. |
| N-08 | Optional customer search, regular suggestions, selected customer / Walk-in reset, add-new action | `suggHTML()` | Customer section; GET `/customers/search/?customer_search=...` → `templates/jobs/customers.html` | Partial. Search/results exist; current page has separate new-name/phone fields instead of prototype suggestion/add-new/reset interaction. |
| N-09 | Notes | `counterView()` | Notes / price difference explanation field | Section; includes reconciliation wording. |
| N-10 | Sticky summary with next job number and customer identity | `summaryHTML()` | `#summary`, `templates/jobs/summary.html` | Section. Next number, selected/new customer identity, price lines and total. |
| N-11 | Price lines and total | `summaryHTML()` | POST `/jobs/price/` updates `#summary` | Section. |
| N-12 | Pay at claim / Cash / GCash segments | `summaryHTML()` | Payment section | Section. Current app additionally exposes optional GCash reference when selected. |
| N-13 | Create job #number; disabled until weight/pieces entered | `summaryHTML()`, `createOrder()` | POST `/jobs/new/` → `/jobs/{number}/` | Section. Numbered create button is disabled until weight or pieces are entered; server validation remains authoritative. |
| N-14 | Sample-price note under create | `summaryHTML()` | Note under create button | Section with different copy. |

## 4. Jobs views and job dialogs

| ID | Prototype page / section / dialog | Source anchor | Current equivalent route / section | Mapping / difference |
|---|---|---|---|---|
| J-01 | Board header, claimed-today count, view segments | `ordersView()` | `/jobs/` header; `templates/jobs/toolbar.html` | Section. |
| J-02 | Stage columns, counts, empty states | `ordersView()` | `/jobs/` → `.board`, `.col` | Section. Simple/full stages come from branch configuration. |
| J-03 | Job cards: tag/price row, customer/payment row, job metadata, hidden-stage pill, overdue state | `orderCard()` | `/jobs/` → `.ocard` | Section. Current cards additionally show paper references; source now groups primary rows like prototype. |
| J-04 | Next-stage button | `advance()` | POST `/jobs/{number}/advance/` | Action; can redirect to machine picker. |
| J-05 | Pencil / manual stage dialog | `editStage()` | `/jobs/{number}/stage/` → `templates/jobs/edit.html` | Dialog from board links with native stage chips; direct page remains available. |
| J-06 | Claim and pay dialog / paid-job release | `claim()` | `/jobs/{number}/claim/` → `templates/jobs/claim.html` | Dialog from board links; server confirmation and direct page remain available for paid and unpaid jobs. |
| J-07 | Claim stub dialog | `showStub()` | `/jobs/{number}/` → `templates/jobs/stub.html` | Dialog from board links, including shop logo, paper provenance and print; direct page remains available. |
| J-08 | Print stub / Done | `showStub()` | Print stub on `/jobs/{number}/`; New job / Job timeline links | Partial. Real print dialog exists; modal Done/return-to-underlying-screen interaction differs. |
| J-09 | List search, Today/Yesterday, date picker, search-state note | `jobsToolbar()` | `/jobs/?view=list&q=...&date=YYYY-MM-DD` | Section. Current explicit Find jobs submit differs from prototype live filtering. |
| J-10 | List rows: job, customer/service, state/dates, payment | `jobListRows()` | `/jobs/?view=list` → `.jlist`, `.jrow` | Section. Rows navigate to timeline page. |
| J-11 | History filters | `jobsToolbar()` | `/jobs/?view=history&q=...&date=YYYY-MM-DD` | Section; shares current list filter form. |
| J-12 | History daily totals / cash / GCash / received / released | `historyRows()` | `/jobs/?view=history` → `.hist-sum` | Section. |
| J-13 | History event rows and job tags | `historyRows()` | `/jobs/?view=history` → `.hist`, `.hist-row` | Section. Event-kind colours distinguish receipt, payment, stage, correction and release. |
| J-14 | Job detail/history dialog: status/payment, price breakdown, timeline, notes, Claim stub / Done | `showJobDetail()`, `jobTimeline()` | `/jobs/{number}/history/` → `templates/jobs/timeline.html` | Dialog from list/history links; status/payment summary, saved price lines, notes and coloured timeline. Direct page remains available. |

## 5. Machines

| ID | Prototype page / section / dialog | Source anchor | Current equivalent route / section | Mapping / difference |
|---|---|---|---|---|
| M-01 | Machines header, loads-today total and state legend | `machinesView()` | `/machines/` → `templates/machines/grid.html` | Section. Loads-today summary and state legend; board-driven starts remain unchanged. |
| M-02 | Category groups and porthole tiles; elapsed time, job, loads today, check flag | `machinesView()`, `tile()` | `/machines/` → `templates/machines/tile.html` and grid | Section. Current actions are separate controls below tiles. |
| M-03 | Idle-machine dialog listing eligible jobs | `machineTap()` | **No Machines-page equivalent by accepted decision.** Use job-board Next → `/jobs/{number}/machine/`. | Amended; see machine-start decision below. |
| M-04 | Next-stage machine picker: idle/busy/out-of-service choices | `machinePicker()` | `/jobs/{number}/machine/?target={stage_id}&expected={stage_id}` → `templates/machines/picker.html` | Page instead of modal. |
| M-05 | Skip, no machine / required reason | `machinePicker()` | Picker page; also `templates/jobs/skip.html` when advance needs a reason | Section/page; action is POST `/jobs/{number}/advance/`. |
| M-06 | Tap running machine to unload | `machineTap()` | POST `/machines/{machine_id}/unload/` from explicit Unload button | Amended presentation; unload behavior exists. |
| M-07 | Paid self-service dialog: per-load service, Cash/GCash, pay-and-start | `selfService()` | `/machines/{machine_id}/start/` → `templates/machines/selfservice.html` | Page instead of modal. |

Accepted behavior amendment: [board-driven machine starts](../outcomes/washday-mvp/decisions/2026-11-03-machine-start.md). Do not treat the absence of job-linked starts on the Machines grid as accidental drift.

## 6. Supplies

| ID | Prototype page / section / dialog | Source anchor | Current equivalent route / section | Mapping / difference |
|---|---|---|---|---|
| U-01 | Supplies heading and Request/Add supply action | `suppliesView()` | `/supplies/` heading; Add supply type link if permitted | Partial. Request is currently a permanently visible form rather than header action/modal. |
| U-02 | Pending-request banner | `suppliesView()` | `/supplies/` → request pills in Request a supply card | Section; different placement and presentation. |
| U-03 | Stock table: Supply / On hand / Used today / Status / Receive | `suppliesView()` | `/supplies/` → `#on-hand` | Section. Supply / On hand / Used today / Status table; Receive is a separate form. |
| U-04 | Recent stock changes beside stock table; job tag / reason / time / quantity | `suppliesView()` | `/supplies/?page=N` → Recent changes | Section. Ledger beside the stock table on wide screens, stacked on phones. |
| U-05 | Recent-changes total and Newer/Older pagination | `suppliesView()` | `/supplies/?page=N` | Partial. Pagination exists; prototype total-change heading differs. |
| U-06 | Full-width Stock count table below stock/log; expected / counted / live difference | `suppliesView()`, `varHTML()` | `/supplies/` → full-width Stock count table below stock/log; POST `/supplies/count/` | Section. Expected/count inputs, live variance pills and explicit partial checkbox. |
| U-07 | Receive selected supply dialog | `transfer()` | `/supplies/` → Receive stock form; POST `/supplies/receive/` | Section instead of modal; dropdown selects supply. |
| U-08 | Request a new supply dialog | `requestSupply()` | `/supplies/` → Request a supply form; POST `/supplies/request/` | Section instead of modal. |
| U-09 | Add supply type dialog | `supplyForm()` | `/supplies/types/new/` → `templates/supplies/new.html`, permission-gated | Dialog from the permitted staff link; owner add-from-request flow is on Dashboard. |
| U-10 | Stock-count history dialog opened from Owner Dashboard | `countHistory()` | `/supplies/` → Count history disclosure list | Section. Staff branch disclosure list and owner Dashboard → `/owner/counts/{branch_id}/` with paginated full/spot history. |

## 7. Owner Dashboard and Live branches

| ID | Prototype section | Source anchor | Current equivalent |
|---|---|---|---|
| O-01 | Dashboard branch filter / All | `dashView()` | `/owner/dashboard/?branch={branch_id}`; All includes every shop branch. |
| O-02 | Sales / loads / received / ready KPIs | `dashView()` | Dashboard KPIs. Sales use payment/self-service events on their actual Manila collection date. |
| O-03 | Machine loads by branch/category | `dashView()` | Dashboard category-coloured bars; simple branches have an explanatory state. |
| O-04 | Needs attention | `dashView()` | Low stock, latest count variances, overdue Ready jobs and open requests. Replication/stale-sync warnings remain unavailable. |
| O-05 | Fulfil request | `supplyForm()` | Dashboard → `/owner/edit/supply/?request={request_id}`. Creating the type marks the request fulfilled atomically. |
| O-06 | Count recency/history | `countHistory()` | Dashboard status → `/owner/counts/{branch_id}/`; paginated full counts and spot checks. |
| O-07 | Branch tablets | `dashView()` | Direct device contact history and authenticated hub sync status; owner sees stale/as-of data and a >30-minute alert. |
| O-08 | Excel sales report | `data-export` | `/owner/reports/sales.xlsx?start=YYYY-MM-DD&end=YYYY-MM-DD&branch=all`; a working daily-collections workbook. A prescribed BIR template was not provided; no BIR compliance claim. |
| O-09 | Live branch selector / mode / freshness | `liveView()` | `/owner/live/?branch={branch_id}`; branch chips, simple-mode indication, server refresh time and polling. Hub staleness is not simulated. |
| O-10 | Running / Check / In-progress / Ready | `liveView()` | Live branch KPIs. Machine KPIs are omitted in simple mode. |
| O-11 | Read-only machines | `liveView()` | Compact porthole grid, elapsed/check state, no staff write controls. |
| O-12 | Read-only job board | `liveView()` | Configured simple/full columns, job tags, payment state and overdue indication; no operational actions. |

## 8. Owner Staff, Machines and Settings

Catalog edit URLs use `/owner/edit/{kind}/{record_id}/`; creation omits `{record_id}`. These open as dialogs from owner links and are also ordinary pages. POST `action=archive` removes/restores entries; supply recipes are removed directly. Historical job lines, stock entries, counts and events remain immutable.

| ID | Prototype feature | Current equivalent | Status / differences |
|---|---|---|---|
| A-01 | Staff branch filters/cards | `/owner/staff/?branch={branch_id}` | Branch chips, avatars, active state and current personal shift. |
| A-02 | Add staff | Staff page / POST `/owner/staff/new/` | Existing secure staff creation with one-time PIN display. |
| A-03 | Edit / PIN / deactivate / branch reassignment | POST `/owner/staff/{staff_id}/` | Staff card editor. Transfers require a fresh branch-unique PIN and end existing shifts. |
| A-04 | Show PIN once | `templates/owner/staff_saved.html` | Dedicated response; no PIN is placed in a toast or stored in plaintext. |
| A-05 | Machine categories | `/owner/machines/`, editor kind `category` | Add/edit/remove/restore; reassign dependent machines/stages before removal. |
| A-06 | Branch machine administration | `/owner/machines/?branch={branch_id}` | Branch cards; labels, category, service status, edit/remove/restore. |
| A-07 | Add machine | Editor kind `machine` | Branch-prefilled creation dialog. |
| A-08 | Minimum kilos | Settings → Operations | Persisted nonnegative minimum. |
| A-09 | PIN master/actions | Settings → Shared-device PIN rules | Existing permission policy, moved into the prototype settings composition. |
| A-10 | Simple mode | Settings → Branches | Persisted per-branch switch; active loads must be unloaded first. |
| A-11 | Check minutes / kilos per load | Settings → Operations | Positive server-validated values. |
| A-12 | Dark theme | Settings → Display / header | Persisted per device. |
| A-13 | Stage table | Settings → Job stages, editor kind `stage` | Name, position, machine category, auto-next and simple visibility. Endpoint stages protected; active jobs/loads prevent removal. |
| A-14 | Add stage | Editor kind `stage` | Inserts into the order and shifts other stages; first/Ready remain endpoints. |
| A-15 | Services | Settings → Services | Add/edit/unit/price/archive/restore. |
| A-16 | Add service | Editor kind `service` | Native form in dialog, validated on server. |
| A-17 | Fees | Settings → Fees; kind `fee` | Name/note/amount/archive/restore. |
| A-18 | Add-ons | Settings → Add-ons; kind `addon` | Name/price/archive/restore. |
| A-19 | Supply recipes | Settings → Add-on supply recipes; kind `recipe` | Add/edit/remove positive per-job quantities. Separate table rather than inline use chips. |
| A-20 | Supply types | Settings → Supply types; kind `supply` | Name/unit/low threshold/washer usage/packing usage/archive/restore. |
| A-21 | Let staff add types | Settings → Operations | Stored permission used by staff supply pages. |
| A-22 | Piece items/sizes | Settings → Piece items and sizes | Item archive/restore and size activation/deactivation; historical prices retained. |
| A-23 | Add piece/size | Editor kinds `piece` / `size` | Server-validated creation/edit dialogs. |
| A-24 | Reset sample data | No live-app action | Prototype-only; intentionally omitted. |

## 9. Cross-cutting dialogs and feedback

| ID | Prototype UI | Source anchor | Current equivalent | Mapping |
|---|---|---|---|---|
| X-01 | PIN modal: staff selection, dots, numeric pad, failure feedback | `withPin()` | Protected POST response → `templates/people/pin.html`; `people/guards.py` | Partial. Action-bound page, not overlay; no standalone PIN route. |
| X-02 | Modal overlay / close / Escape / return focus | `openModal()`, `closeModal()` | Most equivalent flows are standalone pages listed above | Section. Native `<dialog>` enhancement provides close, Escape, focus restoration and ordinary POST forms. Direct routes remain available. |
| X-03 | Success/error toast | `toast()` | Django messages in `base.html` / `auth_base.html` | Implemented for reversible actions; six-second Undo expires in the browser and is enforced on the server. |
| X-04 | Undo action in toast | `act()`, `toast()` | `events/undo.py`, `base.html` | Implemented with device-bound compensating events and stale-state checks. |
| X-05 | Offline toggle / sync simulation | `renderTop()`, `scheduleSync()` | Hub worker and durable server outbox | Prototype simulator omitted; authenticated ordered replication is implemented. Physical rollout qualification remains pending. |

## 10. Current-app pages without a prototype equivalent

These are important when comparing screens: the prototype never designed their page layouts.

| Current route / page | Purpose | Template / source |
|---|---|---|
| `/` without credentials | Welcome / owner-or-staff entry | `templates/people/welcome.html` |
| `/owner/login/` and `/accounts/google/login/` | Allow-listed Google owner sign-in | `templates/owner/login.html`, django-allauth |
| `/owner/` → device/hours sections | Device provisioning, recovery/revocation, branch opening/closing times | `templates/owner/home.html` |
| `/owner/settings/` | Shop name and logo upload/removal | `templates/owner/settings.html`; user-approved contextual branding addition |
| POST `/owner/devices/new/`, POST `/owner/devices/{device_id}/code/` response | Installation link/QR and one-time setup code | `templates/owner/code.html` |
| `/device/start/?invite={device_id}` | Install device / Home Screen instructions | `templates/people/install.html` |
| `/device/setup/?invite={device_id}` | Enter setup code and enrol device | `templates/people/setup.html` |
| `/shift/` | Personal-device staff name/PIN sign-in | `templates/people/shift.html` |
| POST `/shift/end/` | End personal shift | `people/views.py` |
| `/jobs/new/?paper=1` | Paper reconciliation with original dates/times, P number, written total | `templates/jobs/new.html` |

Authentication decisions: [`docs/authentication.md`](authentication.md). Owner/device authentication and shop-context branding supersede the prototype's unauthenticated role/branch simulation.

## 11. Starting points for the next design comparison

Use the IDs above to record screenshots and fixes against a specific page/section:

1. **Shared header:** S-02 (clock), S-06–S-09 (theme/status/navigation coverage).
2. **Intake:** N-01, N-03, N-08, N-10, N-13 (number/identity/hints/customer/create state).
3. **Job dialogs:** J-05–J-08 and J-14 (full pages versus modal composition).
4. **Jobs List/History:** J-09–J-14 (filter controls, event styling, detail hierarchy).
5. **Machines:** M-01–M-07, preserving the accepted board-driven start flow.
6. **Supplies:** U-01–U-10, especially stock/log column placement and full-width count table.
7. **Owner:** P-07–P-11, O-01–O-12, A-01–A-24; distinguish missing pages from layout drift on existing pages.

No visual-fidelity acceptance is implied by this mapping. The next comparison should use the same viewport, zoom, theme, simple/full mode and equivalent data states for each mapped page.

Undo and hub replication implementation, operator commands, supported actions and remaining physical qualification are documented in [offline-and-undo.md](offline-and-undo.md).
