# Prototype → current app page map

Source: [`reference/prototype/index.html`](../reference/prototype/index.html). Mapping date: **4 November 2026**.

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
| P-07 | Owner → Dashboard | `dashView()` | **No equivalent.** `/owner/` is Access and devices, not Dashboard. | Missing | — |
| P-08 | Owner → Live branches | `liveView()` | **No equivalent.** Staff `/jobs/` and `/machines/` are not an owner read-only branch view. | Missing | — |
| P-09 | Owner → Staff | `staffView()` | `/owner/` → Add staff / existing staff administration | Partial | `templates/owner/home.html` |
| P-10 | Owner → Machines | `machinesAdmin()` | **No equivalent.** Staff `/machines/` is operational monitoring, not machine administration. | Missing | — |
| P-11 | Owner → Settings | `settingsView()` | `/owner/` → PIN rules; `/owner/settings/` → branding only | Partial; most prototype settings missing | `templates/owner/home.html`, `templates/owner/settings.html` |

## 2. Shared shell and navigation

| ID | Prototype section | Source anchor | Current equivalent | Mapping / observable source difference |
|---|---|---|---|---|
| S-01 | Shop logo and big blue shop name | `renderTop()` | All staff pages and owner pages: `templates/brand.html`, included by `base.html` / `auth_base.html` | Section. User-approved amendment: signed-out screens show WashDay/generic icon; contextual shops use their own name/logo. |
| S-02 | Current date and time below brand | `renderTop()` | **No equivalent clock.** Contextual staff header currently shows branch name. | Missing. |
| S-03 | Staff tablet / Owner segmented switch | `renderTop()` | `/` offers entry to owner login or staff setup; owner and staff have separate authenticated flows | Amended for authentication. No equivalent in-shell segmented switch. |
| S-04 | Branch selector | `renderTop()` (`#branch`) | Staff scope comes from the enrolled device; owner administration uses branch-specific forms | No equivalent global selector. |
| S-05 | Simple-mode indicator | `renderTop()`, `ordersView()` | `/jobs/` header | Section; located on board rather than global top bar. |
| S-06 | Moon/sun theme button | `renderTop()` | Staff `base.html` → POST `/theme/` | Partial. Staff shell has the control; owner/auth shell has no corresponding theme button. |
| S-07 | Online / synced / offline / pending events pill | `renderTop()`, `scheduleSync()` | Staff header “Connected” pill | Partial. Current pill is static; no offline queue/sync-state equivalent. |
| S-08 | Icon rail, active tab, Ready/check badges | `staffShell()` | Staff `base.html` rail | Partial. SVG links and current-page state exist; Ready/check count badges do not. |
| S-09 | Owner Dashboard / Live branches / Staff / Machines / Settings tabs | `ownerView()` | Owner header: Access and devices / Shop settings | Partial; different destinations and navigation structure. |
| S-10 | Phone bottom navigation / tablet left rail | CSS `.rail`, mobile media query | Shared `static/css/app.css`, staff `base.html` | Section; visual comparison still required. |
| S-11 | Saira Condensed headings, Figtree body, JetBrains Mono numbers; themes/cards/tags | CSS tokens and component rules | `static/css/fonts.css`, `tokens.css`, `app.css` | Shared components exist; this is not proof every page uses equivalent markup. |

## 3. New job / counter sections

All sections below belong to `/jobs/new/` unless another route is listed.

| ID | Prototype section | Source anchor | Current route / section | Mapping / difference |
|---|---|---|---|---|
| N-01 | Screen title, helper text, next-job-number tag | `counterView()` | `templates/jobs/new.html` screen header | Partial. Title/helper exist; next-number tag is absent. Current header adds From paper sheet. |
| N-02 | Service selection chips | `counterView()` | Service section | Section. Native radios styled as chips. |
| N-03 | Clothes-only weight, minimum hint, per-load hint | `counterView()` | Weight section | Partial. Minimum hint exists; dynamic kilos-per-load hint is absent. |
| N-04 | Large kg display and numeric keypad | `counterView()`, `refreshCounter()` | `#kg`, `.keypad`; `static/js/app.js` | Section. Current kg value is directly editable. |
| N-05 | Piece items / sizes / quantity steppers | `counterView()` | Pieces section | Section. |
| N-06 | Add-on chips | `counterView()` | Add-ons within Pieces card | Section. |
| N-07 | Fee chips, including Rush | `counterView()` | Fees within Pieces card | Section. |
| N-08 | Optional customer search, regular suggestions, selected customer / Walk-in reset, add-new action | `suggHTML()` | Customer section; GET `/customers/search/?customer_search=...` → `templates/jobs/customers.html` | Partial. Search/results exist; current page has separate new-name/phone fields instead of prototype suggestion/add-new/reset interaction. |
| N-09 | Notes | `counterView()` | Notes / price difference explanation field | Section; includes reconciliation wording. |
| N-10 | Sticky summary with next job number and customer identity | `summaryHTML()` | `#summary`, `templates/jobs/summary.html` | Partial. Generic Job summary heading; next number/customer heading absent. |
| N-11 | Price lines and total | `summaryHTML()` | POST `/jobs/price/` updates `#summary` | Section. |
| N-12 | Pay at claim / Cash / GCash segments | `summaryHTML()` | Payment section | Section. Current app additionally exposes optional GCash reference when selected. |
| N-13 | Create job #number; disabled until weight/pieces entered | `summaryHTML()`, `createOrder()` | POST `/jobs/new/` → `/jobs/{number}/` | Partial. Current label is Create job & show stub; server validates empty jobs, but button is not initially disabled. |
| N-14 | Sample-price note under create | `summaryHTML()` | Note under create button | Section with different copy. |

## 4. Jobs views and job dialogs

| ID | Prototype page / section / dialog | Source anchor | Current equivalent route / section | Mapping / difference |
|---|---|---|---|---|
| J-01 | Board header, claimed-today count, view segments | `ordersView()` | `/jobs/` header; `templates/jobs/toolbar.html` | Section. |
| J-02 | Stage columns, counts, empty states | `ordersView()` | `/jobs/` → `.board`, `.col` | Section. Simple/full stages come from branch configuration. |
| J-03 | Job cards: tag/price row, customer/payment row, job metadata, hidden-stage pill, overdue state | `orderCard()` | `/jobs/` → `.ocard` | Section. Current cards additionally show paper references; source now groups primary rows like prototype. |
| J-04 | Next-stage button | `advance()` | POST `/jobs/{number}/advance/` | Action; can redirect to machine picker. |
| J-05 | Pencil / manual stage dialog | `editStage()` | `/jobs/{number}/stage/` → `templates/jobs/edit.html` | Page instead of modal; current target stage is a select rather than prototype pick buttons. |
| J-06 | Claim and pay dialog / paid-job release | `claim()` | `/jobs/{number}/claim/` → `templates/jobs/claim.html` | Page instead of modal; current app uses a confirmation page for paid and unpaid jobs. |
| J-07 | Claim stub dialog | `showStub()` | `/jobs/{number}/` → `templates/jobs/stub.html` | Page instead of modal; includes shop logo, paper provenance and dedicated navigation. |
| J-08 | Print stub / Done | `showStub()` | Print stub on `/jobs/{number}/`; New job / Job timeline links | Partial. Real print dialog exists; modal Done/return-to-underlying-screen interaction differs. |
| J-09 | List search, Today/Yesterday, date picker, search-state note | `jobsToolbar()` | `/jobs/?view=list&q=...&date=YYYY-MM-DD` | Section. Current explicit Find jobs submit differs from prototype live filtering. |
| J-10 | List rows: job, customer/service, state/dates, payment | `jobListRows()` | `/jobs/?view=list` → `.jlist`, `.jrow` | Section. Rows navigate to timeline page. |
| J-11 | History filters | `jobsToolbar()` | `/jobs/?view=history&q=...&date=YYYY-MM-DD` | Section; shares current list filter form. |
| J-12 | History daily totals / cash / GCash / received / released | `historyRows()` | `/jobs/?view=history` → `.hist-sum` | Section. |
| J-13 | History event rows and job tags | `historyRows()` | `/jobs/?view=history` → `.hist`, `.hist-row` | Section. Prototype event-kind colour classes are not applied by current history template. |
| J-14 | Job detail/history dialog: status/payment, price breakdown, timeline, notes, Claim stub / Done | `showJobDetail()`, `jobTimeline()` | `/jobs/{number}/history/` → `templates/jobs/timeline.html` | Page instead of modal. Current grouping/order differs; prototype status/payment summary and event-kind colours are not reproduced. |

## 5. Machines

| ID | Prototype page / section / dialog | Source anchor | Current equivalent route / section | Mapping / difference |
|---|---|---|---|---|
| M-01 | Machines header, loads-today total and state legend | `machinesView()` | `/machines/` → `templates/machines/grid.html` | Partial. Current header links to Jobs; no equivalent global loads-today pill or legend. |
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
| U-03 | Stock table: Supply / On hand / Used today / Status / Receive | `suppliesView()` | `/supplies/` → `#on-hand` | Partial. Current layout uses stacked `.stock-row` items, not the prototype table; Receive is in a separate form. |
| U-04 | Recent stock changes beside stock table; job tag / reason / time / quantity | `suppliesView()` | `/supplies/?page=N` → Recent changes | Section. Currently below On hand in left column, not beside it; row structure also differs. |
| U-05 | Recent-changes total and Newer/Older pagination | `suppliesView()` | `/supplies/?page=N` | Partial. Pagination exists; prototype total-change heading differs. |
| U-06 | Full-width Stock count table below stock/log; expected / counted / live difference | `suppliesView()`, `varHTML()` | `/supplies/` → Stock count form in right column; POST `/supplies/count/` | Partial. Current stacked fields have expected placeholders, explicit partial checkbox, and no live difference column. |
| U-07 | Receive selected supply dialog | `transfer()` | `/supplies/` → Receive stock form; POST `/supplies/receive/` | Section instead of modal; dropdown selects supply. |
| U-08 | Request a new supply dialog | `requestSupply()` | `/supplies/` → Request a supply form; POST `/supplies/request/` | Section instead of modal. |
| U-09 | Add supply type dialog | `supplyForm()` | `/supplies/types/new/` → `templates/supplies/new.html`, permission-gated | Page instead of modal. Owner-side add-from-request flow has no equivalent. |
| U-10 | Stock-count history dialog opened from Owner Dashboard | `countHistory()` | `/supplies/` → Count history disclosure list | Partial. Staff branch history exists; owner cross-branch entry and modal do not. |

## 7. Owner Dashboard and Live branches sections

These are **missing owner pages**, not alternative names for existing staff routes.

| ID | Prototype section | Source anchor | Current equivalent |
|---|---|---|---|
| O-01 | Dashboard branch filter / All | `dashView()` | None. |
| O-02 | Sales today (Cash/GCash), Loads today, Received today, Ready/unclaimed KPIs | `dashView()` | None as an owner dashboard. Staff History has daily collection summaries only. |
| O-03 | Loads per machine today by branch/category | `dashView()` | None. Individual staff tiles show per-machine load counts. |
| O-04 | Needs attention: low stock, count variance, overdue jobs, requests, stale sync | `dashView()` | None as an owner attention panel. Some branch-specific indicators exist on staff pages. |
| O-05 | Fulfil request → Add as supply type | `dashView()`, `supplyForm()` | None. |
| O-06 | Stock-count recency/status per branch; open count history | `dashView()`, `countHistory()` | None on owner side; see U-10 for staff-only partial equivalent. |
| O-07 | Branch tablets sync status | `dashView()` | None. `/owner/` lists enrolled devices, not replication status. |
| O-08 | BIR sales report / Export to Excel | `dashView()`, `data-export` handler | None. Prototype export handler only displays a toast; it is not a working exporter. |
| O-09 | Live branches branch selector, simple mode and stale-data banner | `liveView()` | None. |
| O-10 | Live branch Running / Check / In-progress / Ready KPIs | `liveView()` | None. |
| O-11 | Read-only compact machine grid | `liveView()` | None. Staff `/machines/` has write actions and different scope. |
| O-12 | Read-only branch job board | `liveView()`, `orderCard(o, true)` | None. Staff `/jobs/` is interactive. |

## 8. Owner Staff, Machines and Settings sections

| ID | Prototype section / dialog | Source anchor | Current equivalent route / section | Mapping |
|---|---|---|---|---|
| A-01 | Staff branch-filter chips and branch cards | `staffView()` | `/owner/` → existing staff administration | Partial; no dedicated Staff page/filter/avatar/activity-card layout. |
| A-02 | Add staff dialog | `staffForm()` | `/owner/` → Add staff; POST `/owner/staff/new/` | Section, not modal. |
| A-03 | Edit staff, reset/generate PIN, deactivate/reactivate | `staffForm()`, `staffView()` | `/owner/` existing staff forms; POST `/owner/staff/{staff_id}/` | Partial; prototype branch reassignment and dialog layout are not provided. |
| A-04 | PIN shown once after saving | `staffForm()` | Staff-saved response → `templates/owner/staff_saved.html` | Page response, not toast. |
| A-05 | Machine categories table; add/edit/remove category | `machinesAdmin()`, `categoryForm()` | None | Missing. |
| A-06 | Machine branch filters/cards; label/category/service/remove controls | `machinesAdmin()` | None | Missing. |
| A-07 | Add machine dialog | `machineForm()` | None | Missing. |
| A-08 | Minimum kilos | `settingsView()` | None editable in UI; read by intake from stored settings | Missing settings section. |
| A-09 | Ask for staff PIN master switch and action checkboxes | `settingsView()` | `/owner/` → Shared-device PIN rules; POST `/owner/pin-rules/` | Section; placement/control styling differ. |
| A-10 | Branch Simple mode switches | `settingsView()` | None in owner UI; development helper `scripts/set_demo_mode.py` is not a page | Missing. |
| A-11 | Machine check minutes / kilos per load | `settingsView()` | None editable in UI | Missing. |
| A-12 | Settings dark-theme switch | `settingsView()` | Staff header → POST `/theme/`; no owner Settings switch | Partial. |
| A-13 | Job stages table: order/name/machine/category/auto-next/simple/remove | `stagesCard()` | None | Missing. |
| A-14 | Add stage dialog | `stageForm()` | None | Missing. |
| A-15 | Services table: name/unit/price/remove/restore | `settingsView()` | None; intake selection is not catalog administration | Missing. |
| A-16 | Add service dialog | `priceItemForm('svc')` | None | Missing. |
| A-17 | Fees table and add/remove/restore | `settingsView()`, `priceItemForm('fee')` | None | Missing. |
| A-18 | Add-ons table and add/remove/restore | `settingsView()`, `priceItemForm('addon')` | None | Missing. |
| A-19 | Add-on supply recipe dialog and removable use chips | `addonUseForm()` | None | Missing. |
| A-20 | Supply-type table: low level / washer usage / packed-job usage / archive/restore | `settingsView()` | None on owner side; staff `/supplies/types/new/` provides creation only when permitted | Missing owner editor. |
| A-21 | Let staff add supply types switch | `settingsView()` | None editable in owner UI; permission is enforced from stored settings | Missing. |
| A-22 | Piece items / sizes / prices / archive/restore | `settingsView()` | None | Missing. |
| A-23 | Add piece / Add size dialogs | `pieceForm()` | None | Missing. |
| A-24 | Reset sample data | `settingsView()` | No UI equivalent; `seed_demo` is not a reset page | Prototype-only. |

## 9. Cross-cutting dialogs and feedback

| ID | Prototype UI | Source anchor | Current equivalent | Mapping |
|---|---|---|---|---|
| X-01 | PIN modal: staff selection, dots, numeric pad, failure feedback | `withPin()` | Protected POST response → `templates/people/pin.html`; `people/guards.py` | Partial. Action-bound page, not overlay; no standalone PIN route. |
| X-02 | Modal overlay / close / Escape / return focus | `openModal()`, `closeModal()` | Most equivalent flows are standalone pages listed above | Missing shared modal interaction. |
| X-03 | Success/error toast | `toast()` | Django messages in `base.html` / `auth_base.html` | Partial. Current messages lack prototype auto-dismiss/Undo interaction. |
| X-04 | Undo action in toast | `act()`, `toast()` | None | Missing. |
| X-05 | Offline toggle / sync simulation | `renderTop()`, `scheduleSync()` | None | Prototype-only control; actual replication remains unimplemented. |

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
