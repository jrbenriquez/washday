# Washday MVP — outcome plan

## Source and authority

- Human-owned source: [Ivan & Ivy Laundry PRD, updated 3 Nov 2026](../../reference/docs/PRD.md), full version 1 scope. The name `washday-mvp` does **not** trim requirements to a smaller MVP.
- [Reference package README](../../reference/README.md): PRD governs functional rules, data, validation and state changes; [preview](../../reference/prototype/index.html) governs visual presentation and interaction, subject to explicit PRD differences. [Brief](../../reference/docs/brief.md) is subordinate where older decisions differ.
- [Archive](../../reference.zip) was extracted without overwriting existing files into `reference/`; source documents/assets are unchanged. Paths in every outcome resolve from this folder, independently of chat history.
- Assets: [header logo](../../reference/img/logo-header.png), [original logo](../../reference/img/logo-original.jpg), [paper job sheet](../../reference/docs/paper-job-sheet.pdf). PDF is readable, A4 landscape/two A5 halves, but has generic “X & Y Laundry” and a sample row; examples are not real operating data. Preview's “Bula & Banlaw Laundry” is also placeholder branding.
- Fonts Saira Condensed, Figtree and JetBrains Mono are referenced but binaries are not packaged. Actual BIR workbook and real branch/catalog/supply values are absent.

Repository inspection on 3 Nov 2026 found no application source, stack manifests/lockfiles/configuration, AGENTS.md/CLAUDE.md/CONTEXT.md/ADRs, existing outcomes or `.agents/work/` state in this consuming project. It contained `.agents/skills/`, `skills-lock.json` and `reference.zip`. The enclosing git repository is `/Users/johnreienriquez/Code`; sibling projects are not application conventions for Washday. No existing files/IDs/attempt budgets/verdicts were replaced. No implementation, workflow state or agents were started.

## Shared execution constraints

These apply to every outcome; use the linked PRD sections for full rules, not generic stack defaults.

1. **Accepted stack (§3):** Python 3.13, Django 6, server templates + HTMX; DRF only for sync. SQLite locally/hubs (hub WAL on SSD), PostgreSQL cloud. One codebase and same Docker image, final `APP_ROLE=hub|cloud`, amd64 + arm64. django-allauth/Google owner allow-list, openpyxl exports, Tailscale-only remote hub access. Preserve prescribed `core`, `people`, `customers`, `catalog`, `jobs`, `machines`, `supplies`, `events`, `owner` ownership, routes and reusable partials (§§3,7). No React, bundler, client database, service-worker sync or unapproved framework/dependency. No framework replacement or upgrade is implied.
2. **Data/tenant safety (§§3–4,8):** UUID primary keys; decimal money `(10,2)` and kg `(6,1)`; current-shop middleware/default tenant-scoped base manager on every shop-owned model, explicit unscoped access only for genuine operator work. Shop scope from owner link or enrolled device/hub branch, never request-selected tenant. Cross-shop record requests return 404. Operational branch scope also enforced. State writes append immutable Events in the same transaction, per-branch sequence; never edit/delete Events, StockCounts or historical price snapshots. Test model-scoping coverage continuously as models arrive. Production v1 has one Shop; a second exists only for isolation tests.
3. **Content/design (§§5–8):** “job”, never “order”/“ticket”; “claim stub”. English, ₱ with 2 decimals, kg with 1 decimal, Asia/Manila calendar days. Actual Shop name/logo; local fonts/icons/logo. Copy preview `:root` tokens into `static/css/tokens.css`; light default, dark via `data-app-theme` cookie per device. Prototype token block governs visual discrepancies (e.g. distinct dark `--teal` vs `--tag`). Teal punched tags, porthole machines, perforated stub. ≥44 px targets, ≥56 px primary controls, labels/real buttons/visible focus/text+colour status; only board container may scroll horizontally; bottom navigation below 760 px. Compare 390/1280 px light/dark and support 360 px+. Every action gives toast; reversible actions use six-second server compensation, not preview snapshots.
4. **Preview boundaries:** Browser `S`/localStorage, sample data/reset, simulated cloud status, branch dropdown, owner/staff demo switch, blanket PIN, JS business calculations and Google-hosted fonts are disposable examples. Production persistence/rules belong to server; staff branch fixed by enrolment. `seed_demo` development-only. Explicit PRD defaults (Rush ₱50 “Same day”, stages, categories, check-after 90) are distinct from unspecified real prices/recipes/names. Real values are collected before pilot, not invented or used to block all local development.
5. **Verification:** Required pytest suites stay with the behavior they protect: pricing, transitions, stale actions, stock, paper time/duplicate P refs, device expiry/use/lockouts, model scoping and cross-shop 404, sync replay/out-of-order. Required Cypress: lifecycle, stock count, paper entry; rerun both modes after split. Physical browser/printing, network latency, 4-hour router outage, full-day laptop dry run, 7-day N100/UPS and two-week pilots need their own evidence. Planned/unrun checks never count as acceptance. Later integrations/changes require regressions of earlier owners; historical completion alone is insufficient.
6. **Delivery (§9):** Milestones 1 counter → 2 machines/supplies → 3 people/Undo → 4 owner → direct + simple live pilot → 5 laptop hub split/outage → full-day home dry run → real N100 kit seven days → hub/full pilot two weeks → remaining branches/spare. Build locally with explicit fixtures before production auth is complete; do not expose that development setup as a release. Hardware, external access and observation periods are real prerequisites, not agent-created success claims.

## Owner clarifications

These decisions were supplied by the user during outcome planning on 3 Nov 2026. They supplement the source; the extracted human-owned PRD remains unchanged.

| ID | Approved clarification | Affected outcomes |
| --- | --- | --- |
| D-01 | Add per-branch opening_time alongside closing_time to define direct-device offline-alert opening hours. Do not invent real times. | settings AC-02; monitoring AC-06; direct-pilot AC-01 |
| D-02 | For a custom category with a linked stage, Machines-screen job choices are that stage or its immediately preceding active stage, not all earlier/later stages. Example: Steam press linked to Pressing accepts Drying/Pressing. Default washer Received/Washing and dryer Washing/Drying remain unchanged. | machines AC-03; settings AC-07; sync AC-06 |
| D-03 | For offline duplicate supplies, owner chooses surviving type and its settings; preserve both histories and reconcile references/balances without deleting Events. | sync AC-04 |
| D-04 | Personal phones in simple mode open Jobs after shift sign-in; full-mode default remains Machines. | people AC-04 |
| D-05 | User confirmed a busy machine cannot accept another load; it shows the current job/stage and moving the job onward frees it. Preserve PRD's explicit Unload action and manual-override exception (override leaves load running). This does not resolve idle-machine mapping when several stages match. | machines AC-02/AC-05; progression AC-04 |

## Outcome index and readiness

IDs are fully prefixed `washday-mvp-…` and stable. Table abbreviations in the coverage section refer to these full IDs. `ready` means sufficiently specified **and prerequisite evidence is currently satisfied**, not merely graph-eligible in the future. No prerequisite implementation evidence exists today. A dependent outcome can be well specified yet blocked. Draft criteria are called out explicitly.

| Order | Outcome ID / document | Prerequisite outcome IDs | Current readiness |
| --- | --- | --- | --- |
| 1 | [washday-mvp-intake](washday-mvp-intake.md) | none | **ready** for local implementation; self-host font acquisition needed for visual verification |
| 2 | [washday-mvp-progression](washday-mvp-progression.md) | washday-mvp-intake | **blocked:** intake evidence |
| 3 | [washday-mvp-history](washday-mvp-history.md) | washday-mvp-progression | **blocked:** progression evidence |
| 4 | [washday-mvp-machines](washday-mvp-machines.md) | washday-mvp-history | **blocked:** history evidence; draft AC-03 multi/no-stage mapping |
| 5 | [washday-mvp-supplies](washday-mvp-supplies.md) | washday-mvp-machines | **blocked:** machines evidence |
| 6 | [washday-mvp-people](washday-mvp-people.md) | washday-mvp-supplies | **blocked:** supplies evidence |
| 7 | [washday-mvp-settings](washday-mvp-settings.md) | washday-mvp-people | **blocked:** people evidence; inherited mapping draft for custom configurations |
| 8 | [washday-mvp-monitoring](washday-mvp-monitoring.md) | washday-mvp-settings | **blocked:** settings evidence; actual network timing access needed |
| 9 | [washday-mvp-reports](washday-mvp-reports.md) | washday-mvp-monitoring | **blocked:** monitoring evidence; draft AC-03 missing BIR sample |
| 10 | [washday-mvp-cloud-release](washday-mvp-cloud-release.md) | washday-mvp-reports | **blocked:** reports evidence; VPS/domain/OAuth/devices/networks/JR review |
| 11 | [washday-mvp-direct-pilot](washday-mvp-direct-pilot.md) | washday-mvp-cloud-release | **blocked:** release evidence; real data/training/two-week observation |
| 12 | [washday-mvp-sync](washday-mvp-sync.md) | washday-mvp-direct-pilot | **blocked:** pilot evidence; laptop/router/cloud/device access; inherited mapping draft |
| 13 | [washday-mvp-hub-operations](washday-mvp-hub-operations.md) | washday-mvp-sync | **blocked:** sync evidence; Ubuntu/Tailscale/recovery access |
| 14 | [washday-mvp-hardware](washday-mvp-hardware.md) | washday-mvp-hub-operations | **blocked:** operations evidence; N100/UPS/router/seven days |
| 15 | [washday-mvp-hub-rollout](washday-mvp-hub-rollout.md) | washday-mvp-hardware | **blocked:** hardware evidence; two-week hub pilot, remaining branches/spare |

### Suggested execution order

Follow table order 1–15. The dependency chain is intentionally serial to preserve the source milestone/pilot gates and bound integration on shared job, stage, event, settings and template files. There are no unknown IDs or cycles. Dependencies are evidence requirements, not completed promises. Full-mode picker and stock integrations introduced later must regress the milestone-1 job contract; simple-mode/explicit skip paths give the earlier counter slices useful verification boundaries.

Milestone mapping: 1 = outcomes 1–3; 2 = 4–5; 3 = 6; 4 = 7–9, with release integration 10; direct pilot = 11; 5 = 12–13; hardware/pilot/rollout = 14–15. Fifteen outcomes reflect distinct observable verification boundaries (including long-running operational checks), not a fixed quota or technical-layer split. No standalone database/UI/foundation outcome exists. No parallel implementation is proposed; planning does not authorise delegation. Existing coordinator attempt limits apply per outcome; splitting does not reset an exhausted budget. There are currently no saved attempts to reconcile.

## Coverage table

Local labels below are stable planning labels for unnumbered source bullets. Short owner names mean full `washday-mvp-<name>` IDs in the index. Criterion ranges are inclusive. Primary ownership is assigned once; later integration references are regressions, not duplicate implementation ownership.

| Source section + local label | Required behavior/target | Primary outcome / criteria | Integration/evidence |
| --- | --- | --- | --- |
| §1 GOAL-operations; §2 V1-jobs | Counter records jobs across three branches | intake AC-01–10; progression AC-01–09 | cloud-release AC-02; hub-rollout AC-06 |
| §1 SUCCESS-intake | Median first tap → create ≤30 seconds after 2-week pilot | direct-pilot AC-02 | hub-rollout AC-02 |
| §1 SUCCESS-load-links | ≥90% claimed full-mode jobs have washer+dryer loads | hub-rollout AC-02 | machines AC-03–06 provides data |
| §1 SUCCESS-count-days | Every branch full count ≥6/7 days | hub-rollout AC-03 | direct-pilot AC-03 (pilot branch only) |
| §1 SUCCESS-hub-outage | 4-hour outage, zero loss/no visible staff effect | sync AC-07 | hub-rollout AC-04 |
| §1 SUCCESS-paper-recovery | Every paper job entered within one working day after internet return | direct-pilot AC-04 | hub-rollout AC-05 |
| §1 SUCCESS-owner-freshness | Online events visible within 1 minute | monitoring AC-08 | sync AC-08; direct-pilot AC-05 |
| §1 MULTISHOP; §2 V1-tenancy; §3 TENANT; §4 TENANCY | One production Shop, all shop-owned data scoped; second test shop; foreign 404; explicit unscoped manager | intake AC-10 + shared constraints | settings AC-01/11; sync AC-01–03/06; cloud-release AC-01/02/06 |
| §3 STACK; §3 APPS; §3 ROUTES | Accepted Python/Django/HTMX, apps/routes, databases, DRF limit, allauth/openpyxl, same image | intake constraints; settings AC-01; reports AC-01; sync AC-01/06 | Shared constraints apply per behavior; hub-operations AC-05 |
| §3 SYNC-transaction; §4 MODEL-events/keys/decimals | UUID keys, transactional immutable Event/state, branch seq, money/kg precision | intake AC-04/10 | every write owner; sync AC-01/02 |
| §4 MODEL-customer; §5 NEW-customer | Optional shop-shared name/phone customer lookup/create | intake AC-01/10 | history AC-01/02 |
| §4 MODEL-catalog; §6 PRICING-presence | Clothes/pieces/both, kg>0 or piece; optional Heavy items | intake AC-01–03 | settings AC-04/05 |
| §6 PRICING-kg/load/pieces | Minimum kg, ceil load pricing, zero-kg no service/minimum, piece size quantities | intake AC-02 | pytest; cloud-release AC-02 |
| §6 PRICING-extras/round/snapshot | Add-ons, fees, half-up per line, sum rounded lines; immutable existing prices | intake AC-02/03 | settings AC-04/05; reports AC-02 |
| §6 NUMBER-sequence | Branch number ×1000+1, unique increments, owner branch+number | intake AC-04 | monitoring AC-01/07 scoped branch view |
| §5 NEW-stub; §7 SIGNATURE-stub; §9 CHECK-print | Stub contents, real received time, paper provenance, digital/device print, slip styling | intake AC-07–09 | cloud-release AC-03 |
| §5 JOBS-board; §6 STAGES-default | Default configured stages/cards, independent Next/Claim, 20-second board refresh | progression AC-01/02 | settings AC-07; monitoring AC-07 |
| §6 STAGES-picker/skip | Stage-category/all picker, busy/OOS disabled, load parity, reason-required skip | machines AC-04 | supplies AC-02; Cypress lifecycle |
| §6 STAGES-leave/unload/start | Normal departure ends load; last-unload auto-next unless next asks; grid start advances eligible job | machines AC-03/05 | custom mapping draft noted explicitly |
| §6 STAGES-override | Any-stage correction, optional reason, Event copy, no picker/open load retained, release only Claim | progression AC-04 | history AC-03; people AC-05 |
| §6 STAGES-stale | Expected-stage request refusal and refresh with actual stage | progression AC-05 | machines AC-07; people AC-08 |
| §6 SIMPLE-staff/default/hidden | Direct+simple default, shown stages only, hidden-stage label, preserve stages on return, no machines/picker, unchanged other flows | progression AC-02/03 | machines AC-07; settings AC-02/07 |
| §6 SIMPLE-stock | No washer deductions; packing/add-on still apply | supplies AC-02/03 | paper/simple Cypress regressions |
| §6 SIMPLE-owner | Hide machines/counts, badge, omit simple branches from machine chart | monitoring AC-02 | hub-rollout AC-01 |
| §6 CLAIM-payment; §5 CLAIM | Cash/GCash at intake or unpaid claim, optional reference, retain paid time, no double collection | intake AC-05; progression AC-06 (claim owner) | reports AC-01/02; people AC-05/06 |
| §6 PAPER-sheet/steps | A4 landscape 100% two A5; header/Part A/B/footer/P numbering; stock/machines absent; paper kit and reconciliation | cloud-release AC-07 | direct-pilot AC-01/04; supplied PDF |
| §6 PAPER-intake/date/duplicate | Sheet received/paid times vs created_at, today to −7 days/no future, P uniqueness branch/date, existing-job warning | intake AC-06/07 | pytest paper boundaries |
| §6 PAPER-release/ready | Part B time-out/payment, Ready tick, no machine picker/loads, normal packing | progression AC-07 | supplies AC-03; Cypress paper |
| §6 PAPER-price-difference | Entry-time prices; show both totals; keep app total/explanation | intake AC-07 | direct-pilot AC-04 |
| §6 PAPER-search/provenance | P search, stub/timeline paper received/entered-by distinction | history AC-01/05; intake AC-07/08 (stub owner) | reports AC-02 |
| §6 PAPER-report-days | Actual received/paid/claimed dates govern list/history/dashboard/BIR/kg | history AC-02/04/05 | monitoring AC-01; reports AC-02 |
| §6 HISTORY-date/search/list | Today/Yesterday/picker, all-date search fields, released jobs, every required row field | history AC-01/02 | screenshots and branch isolation |
| §6 HISTORY-timeline | Event-derived receive/load/unload/stage/payment/release, actors, lines, stub | history AC-03/06 | machines AC-06; people AC-06/08 |
| §6 HISTORY-day | All branch Events newest first, received/released/total/Cash/GCash including self-service | history AC-04/06 | supplies/people integrate their events |
| §6 MACHINE-state/eligibility | Category groups, time only, idle-only start, one open load, explicit default eligibility | machines AC-01–03 | D-02/D-05; multi-match draft |
| §6 MACHINE-unload/flag/today | Unloaded duration, flag ≥check_after_min (default 90), loads since Manila midnight | machines AC-01/02/06 | monitoring AC-01/07 |
| §6 MACHINE-selfservice | Hidden without active per-load service, none preloaded, immediate Cash/GCash, sales | machines AC-06 | history AC-04; monitoring AC-01 |
| §6 SUPPLY-ledger/deductions | Ledger balance; add-on/load/first-Ready usage; archived skipped | supplies AC-01–03 | settings AC-04/06; Undo regression |
| §5 SUPPLY-recent; §6 SUPPLY-receive | Positive receipt; newest 10/page Newer/Older, reason/amount/time/job timeline | supplies AC-04 | history link isolation |
| §6 SUPPLY-count | Anytime full/partial expected/count/variance, nonzero adjustment, immutable counts | supplies AC-05/08 | Cypress count |
| §6 SUPPLY-variance/low | Magnitude 1–3 warning, >3 critical, on hand ≤ low | supplies AC-01/06 | monitoring AC-03/04 |
| §6 SUPPLY-freshness/history | Latest full: today/yesterday green, 2 days orange, ≥3/never red; partial no refresh; full history/actors | monitoring AC-04 | direct/hub count-day observations |
| §6 SUPPLY-permission/name | Owner-only unless unlocked, requests, case-insensitive names, archived restore | supplies AC-07 | settings AC-06; monitoring AC-05 |
| §6 ALERT-stock/count/ready/request | All required needs-attention triggers, one count alert/supply, Ready >2 days/unpaid | monitoring AC-03/05 | clock-threshold fixtures |
| §6 ALERT-hub/direct | >30-minute hub sync alert; direct unseen during opening hours “may be on paper” | monitoring AC-06 | D-01; sync AC-08 |
| §6 TOTAL-sales/kg/ready | Paid-time sales + self-service start, received-time kg, Ready/unclaimed due | monitoring AC-01 | reports AC-01/02; replicated regression |
| §6 PEOPLE-install/setup | QR only install page; home-screen-only key save, 6 digits/15 min/single use, correct branch | people AC-01/02 | cloud-release AC-03 actual Android/iPad/iPhone |
| §6 PEOPLE-key/recovery | Invalid/revoked key denied immediately; lost-key message/new code; no rescan required | people AC-03 | settings AC-10; cloud-release AC-03 |
| §6 PEOPLE-shifts | Personal sign-in/open shift/actor, End shift/closing auto-end, shared no shift | people AC-04/07 | D-04; settings AC-09 |
| §6 PEOPLE-PIN | 4-digit hashed branch-active unique PIN; shared selected rules/defaults; paper rules; 5 tries/1-minute lock | people AC-02/05 | settings AC-09; pytest lockouts |
| §6 STAGES-Undo; §7 FEEDBACK | Last reversible action ≤6 seconds same device, compensating Event, original history retained | people AC-06 | history summaries; all mutation regressions |
| §5 OWNER-signin/scope; §6 PEOPLE-owner | Google ShopOwner allow-list, shop-bound session, no foreign branch pickers | settings AC-01 | cloud-release AC-01/02 |
| §5 OWNER-settings | Save-on-change/version, min kilo first, PIN flags, kilos/load, check time, per-device theme | settings AC-03 | sync AC-03 settings propagation |
| §5 OWNER-catalog; §9 CHECK-catalog | Service name/unit/price/archive, add-on recipes, fee list, piece sizes/prices/archive | settings AC-04/05 | staff intake + old-line regression |
| §5 OWNER-stages | Stage rename/middle CRUD/order, first/last fixed, in-use removal denied, machine/simple flags | settings AC-07 | machines/progression regression; mapping draft |
| §5 OWNER-machines | Category name/prefix/wash-use, removal guard, machine labels unique/recategorise/OOS/archive idle/history | settings AC-08 | machines AC-02/04 |
| §5 OWNER-staff | Staff tab position/filter, add/edit/Generate/reset/PIN once/deactivate/reactivate/history | settings AC-09 | people AC-04/05 |
| §5 OWNER-devices | Branch devices/kind/name/seen/revoke/code time-left, add/new-code instructions | settings AC-10 | people AC-01–03 |
| §5 OWNER-live; §7 PARTIAL-readonly | Reused readonly board/tile, 20-second refresh, as-of offline state | monitoring AC-07 | sync AC-08 |
| §3 EXPORT; §5 BIR; §9 CHECK-BIR | Daily branch/method date-range Excel, actual owner's layout | reports AC-01–03 | **Unresolved:** sample absent; exact layout draft |
| §3 SYNC-batch/ack | Every 30 sec, ≤500, backoff, UUID idempotency, seq ack/gaps/reordered/replayed safe | sync AC-02 | 4-hour event-set reconciliation |
| §3 SYNC-pull/direction | Startup/every 5 min/version atomic own-shop settings; ops up/catalog down | sync AC-03 | both-role staff suites |
| §3 SYNC-supply-exception | Offline staff-type UUID up; duplicate names retained/owner merge | sync AC-04 | D-03, replay original IDs after merge |
| §3 MODES/default/serve | Direct default, hub only own branch, cloud refuses hub staff, identical events/direct no outbox | sync AC-01 | progression AC-02; cloud-release AC-01 |
| §3 MODES-migrate/bootstrap | Direct bootstrap/after-closing switch/re-enrol; hub drain/empty switch/re-enrol, zero loss/dup | sync AC-05 | hub-rollout AC-01 |
| §7 DESIGN-all | Tokens/theme/type/logo/signature details/navigation/touch/overflow/toast/reused templates | intake AC-09 establishes; each UI owner owns its screens | cloud-release AC-05 full comparison |
| §8 SPEED | Hub <200 ms pages/<300 ms actions; direct <1 sec; owner <2 sec | sync AC-08 (hub); cloud-release AC-04 (direct/owner) | hardware AC-02 real hub |
| §8 DEVICE | Current Android tablet/phone both roles; iPad/iPhone Safari direct; installed storage; ≥360 px | cloud-release AC-03/05 | sync AC-06; per-screen acceptance |
| §8 OFFLINE-retention | Hub no visible internet-loss effect; ≥30 days unsent | sync AC-07 | hub-rollout AC-04 |
| §8 OFFLINE-UPS | Hub + router at least 2 hours | hardware AC-04 | actual measured load/runtime |
| §8 HUBFAIL-restore | Spare restores all synced branch events <30 min; paper fallback | hub-operations AC-02/03 | hub-rollout AC-05/06 |
| §8 SAFETY-backups | Hub WAL/nightly snapshots keep 7; cloud daily PG keep 30; immutable data | hub-operations AC-01 | cloud-release AC-06 cloud gate |
| §8 TENANT-export/restore | Per-shop CSV or JSON offboarding/privacy; no leakage in any query/page/export/sync/restore | reports AC-04/05; hub-operations AC-02/06 (restore owner) | isolation checks per behavior; sync AC-02/03 |
| §8 SECURITY | Hashed secrets, setup/PIN lockouts, HTTPS cloud, enrolled branch hub auth, owner allow-list, Tailscale | people AC-02/05; cloud-release AC-01; sync AC-02; hub-operations AC-05 | tests at owning boundaries |
| §8 ACCESS/LOCALE | Real labelled controls/focus/text status/min targets, English/₱/kg/Manila | shared constraints + each UI criterion | cloud-release AC-05 |
| §8 UPDATE | Nightly after-closing image pull; previous-version Event-compatible migration | hub-operations AC-04 | hardware AC-05 |
| §8 TEST-required | Named pytest suites + Cypress lifecycle/count/paper, outage, both roles, isolation model-coverage | each behavior's verification/AC | cloud-release AC-02; sync AC-06/07 |
| §9 DELIVERY-review | JR milestone review, prescribed build order | cloud-release AC-02 + dependency chain | source rollout gates retained |
| §9 ROLLOUT-direct/home/hardware/hub/others | Direct two weeks → laptop 4h/full-day → N100 7 days → hub two weeks → other branches/spare once | direct-pilot AC-01–05; sync AC-07/09; hardware AC-01–06; hub-rollout AC-01–07 | human/physical/elapsed prerequisites explicit |
| §9 CHECK-multiarch | Image builds and tests amd64 and arm64 | sync AC-06 | hardware actual amd64 |
| §9 COLLECT-owner-input | Real prices/services/recipes/branches/hours/BIR sample before pilot | direct-pilot AC-01; reports AC-03 | external, not blanket build blocker |
| §10 SETUP-cloud/branch/network | VPS/domain/PG/backups; Ubuntu/ID/Tailscale; isolation off/main network/reserved IP/UPS/Ethernet or saved Wi-Fi | cloud-release AC-01/06; hub-operations AC-05; hardware AC-01 | no purchases/provisioning by plan |
| §10 KIT/procurement | Devices first; one N100/UPS kit before remaining purchases; existing router reuse/SIM hub option, spare | hardware constraints/AC-01/06; hub-rollout AC-06 | quoted prices are source estimates, not acceptance thresholds |
| §2 EXCLUSIONS; §11 LATER | All excluded/future work preserved below | all outcomes' boundaries | not silently added as prerequisites |

## Explicit exclusions

Preserve PRD §2 exclusions: SMS/other customer notifications; official receipts; thermal claim-stub printing (v1.1); direct Bluetooth printing; sign-up/billing/plans/self-serve onboarding for other shops; loyalty/promos/discounts; maintenance logs; customer-facing tracking; physical NFC/e-ink job tags; separate trimmed floor mode for phones.

§11 is recorded future work, **not v1 acceptance**: LAN ESC/POS printer, python-escpos, port 9100, auto printing/printer settings/test print/reprint/failure toast/QR stub and ≤2-second printer check; optional later cloud-polling printers; Bluetooth browser printing and vendor-SDK POS handhelds not planned. Keep current digital/device-dialog printing and avoid blocking a later addition, without building speculative printer infrastructure.

## Unresolved decisions and external blockers

| Label | Missing decision/asset/evidence | Affected criteria | Proposed interpretation / status |
| --- | --- | --- | --- |
| Q-01 | Idle machine category maps to several stages, wildcard stages, or none | machines AC-03; settings AC-07/08; sync AC-06 | **Draft.** No approved target-selection rule. User clarified busy-machine exclusion, which already applies; do not treat it as choosing a rule for idle machines. Candidate discussed: eligible-stage picker; no-match self-service only. **Not approved.** Default/single-linked-category behavior is specified. |
| Q-02 | Owner's current BIR Excel workbook | reports AC-03; cloud release → pilot chain | **Draft exact-layout acceptance.** No replacement format invented; aggregation/software work otherwise specified. |
| E-01 | Self-host font binaries absent | intake AC-09; all UI local typography; release/sync | Obtain specified fonts for implementation/verification; prototype Google Fonts link isn't offline evidence. Logo/PDF/preview are accessible. |
| E-02 | Real prices/catalog/supply recipes/thresholds, branch names/codes/opening/closing, staff/owner accounts | direct-pilot AC-01; all live rollout | Owner inputs before pilot; explicit local fixtures allowed earlier. No invented operational values. |
| E-03 | Real unusual/overnight opening schedule if any | monitoring AC-06; direct-pilot outage recovery | Ordinary opening_time/closing_time approved D-01; resolve only if actual schedule needs more. Working-day context is required for the one-working-day paper target. |
| E-04 | VPS/domain/HTTPS/OAuth/network/Google allow-list access; actual Android/iPad/iPhone devices; JR reviews | cloud-release AC-01–07 | External prerequisites; no production access inferred from PRD. |
| E-05 | Two-week direct observation/training/paper reconciliation | direct-pilot AC-01–05; sync dependency | Live evidence, not generated test data. |
| E-06 | Laptop/router internet-cut access/shared+personal devices, cloud test, both build architectures | sync AC-06–09 | Four-hour outage + full-day home dry run required; keep Wi-Fi connected when cutting modem internet. |
| E-07 | Ubuntu/Tailscale/backup recovery environment; actual N100/UPS/router and seven days | hub-operations AC-01–06; hardware AC-01–06 | Laptop cannot prove physical tests. Purchases/physical work controlled by owner. |
| E-08 | Two-week hub/full pilot; additional branch devices/hubs/spare and live count/load metrics | hub-rollout AC-01–07 | Follow staged procurement/rollout, spare tested once. |
| E-09 | Pilot suitability of generic-brand/sample paper PDF | cloud-release AC-07; direct-pilot AC-01 | Source asset left intact. Review training/print use; do not mistake sample row/name for real data or silently rewrite approved sheet. |

Q-01 can be resolved later while unaffected specified work is implemented, but unresolved acceptance remains draft and prevents full PASS for its owning outcome. Q-02 blocks exact BIR acceptance only, not all report development. External prerequisites must be evidenced before their outcome becomes ready. Approved D-01–D-05 are recorded above, not proposed defaults.

## Planning review and execution

- Coverage includes source behavior, thresholds, failure paths, cross-cutting targets, rollout gates and unresolved requirements; no feature is assigned only to a final test backlog.
- Primary behavior owners and local AC IDs are stable; integration outcomes reference earlier owners and demand current regressions. Shared safety/design constraints intentionally repeat.
- Dependencies form a known, acyclic chain; no framework migration, speculative dependency upgrade, execution state reset or sibling set revision is included.
- Planning inspection/readability/link/structure checks are not product acceptance. No product tests, browser rendering, deployment, physical checks or pilots have run.

Only a subsequent execution request starts the workflow:

```text
orchestrate-work for outcomes/washday-mvp
```

This selects the group with dependency scheduling, saved progress and verification defaults; the coordinator recalculates readiness from actual evidence. To select a single document:

```text
orchestrate-work for outcomes/washday-mvp/washday-mvp-intake.md
```
