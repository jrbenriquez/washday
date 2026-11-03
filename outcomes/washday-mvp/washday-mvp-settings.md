# Let the authorised owner configure the shop and its people

## Title and ID
`washday-mvp-settings` — Owner sign-in and operational administration (milestone 4).

## Source
[PRD](../../reference/docs/PRD.md) §§3–4 owner routes/tenancy/catalog; §5 Owner screens; §6 stages/machines/supplies/people; §§7–8; §9 milestone 4/checklist lines 511, 514, 519–521, 534–535, 540. D-01/D-02 in [index](README.md#owner-clarifications).

## References
[Preview](../../reference/prototype/index.html): Owner → Settings, Staff, Machines; `settingsView`, `stagesCard`, `pieceForm`, `addonUseForm`, `staffView`, `machinesAdmin`. PRD-specified Devices UI has no full preview. [Package authority](../../reference/README.md), [logo](../../reference/img/logo-header.png), [shared constraints](README.md#shared-execution-constraints).

## Desired outcome
A Google-allow-listed owner can administer only her shop's branch configuration, catalogs, stages, machines, staff and devices, and staff see valid changes without old jobs changing price.

## Dependencies
`washday-mvp-people`: enrolment, actors, PINs and complete staff behaviors exist for validating the owner's changes.

## Acceptance criteria
- **AC-01:** django-allauth Google sign-in succeeds only for a ShopOwner email, binds the session/current-shop to that shop, and rejects other owners/emails from accessing its records. Owner filters/pickers show only that shop; foreign identifiers return 404. No shop picker, shop-in-URL selector or self-service sign-up appears. Owner routes are cloud-only in the final role split.
- **AC-02:** Branches can be configured with real names/codes, opening time (approved D-01), closing time, direct/hub and simple/full modes; new branches default direct + simple unless explicitly chosen otherwise. Direct branches show the exact outage/paper warning from §3. Until sync bootstrap/drain is implemented, a mode change cannot misleadingly activate an unprepared hub or unsafe transition.
- **AC-03:** Settings saves each field on change, validates rather than accepting invalid values, and increments settings version on accepted shared changes. Minimum kilos is the first card above PIN rules; min_kg, kg_per_load, check_after_min, master/action PIN flags and staff_can_add_supply are editable. Device theme is a cookie preference, not a shop-wide settings override.
- **AC-04:** Owner can add/rename/change unit (kg/load)/price/archive services, including optional heavy-items pricing; add/rename/reprice/archive add-ons and set/remove their supply uses; add/edit/archive fees (name/note/amount, Rush seeded as specified). Staff intake reflects changes; existing JobLines/totals and self-service collection snapshots remain unchanged.
- **AC-05:** Owner can add piece items, add/remove sizes, change size prices and archive items. A one-price item uses Each. Changes appear in intake; past pieces/price evidence survives removed sizes or archived items.
- **AC-06:** Owner can add supply types, set unit/low threshold/per-load/per-packed usage, archive/restore and unlock staff creation. Case-insensitive active/archived duplicate names cannot be added normally. Archived types remain historical but disappear from staff/deductions; new types start with zero ledger balance until branch receipt/count. Setting AddOnUse affects actual deduction tests.
- **AC-07:** Owner can rename any stage; add/archive/reorder middle stages and set machine demand/category-or-any, move-on-unload and Show in simple mode (middle default off). First/last remain fixed in position and cannot be removed; a stage holding jobs cannot be removed. Board and simple-mode rules reflect accepted changes without losing job stages. Custom machine eligibility follows D-02.
- **AC-08:** Machines administration has a branch filter and category groups; owner adds/renames/removes categories with prefix/wash-use, but cannot remove a category used by a machine/stage. Add machine suggests prefix labels; labels unique per branch. Relabel, recategorise, out-of-service/back and archive idle machines work while preserving history; busy-machine removal is refused and out-of-service machines cannot start loads.
- **AC-09:** Staff tab is between Live branches and Machines, filtered by branch. Owner adds/edits name/branch/PIN, generates or resets a 4-digit PIN, deactivates/reactivates. PIN unique among active staff in the branch, shown once on set, stored hashed; old reset PIN and inactive PIN stop working, past actions remain. Invalid PIN/branch collisions are refused server-side.
- **AC-10:** Devices lists branch/kind/name/last seen/revoke and unused code expiry countdown. Add device produces QR to install page and a single-use 6-digit code valid 15 minutes plus correct instructions; New code replaces unused code for an existing device; revoke blocks access. Branch/kind/address are not taken from an untrusted submitted key.
- **AC-11:** Every configuration mutation preserves Event/tenant requirements, and forbidden changes leave no partial writes. Staff-side regressions prove pricing snapshots, recipes, stages, PIN/device policies respond to edits. All owner screens honor shared themes, responsive/accessibility/locale constraints and use production brand/assets rather than sample reset controls.

## Constraints
[Shared constraints](README.md#shared-execution-constraints); use prescribed apps and Google integration, not a replacement auth system. Do not add a dependency without approval; libraries explicitly named by PRD are accepted choices. Fixtures provision the first Shop/ShopOwner locally; real owner email/Google OAuth environment is an external release prerequisite. Catalog/settings flow down to hubs only after sync exists.

## Out of scope
Dashboard/live/request conversion: `washday-mvp-monitoring`; BIR/privacy exports: `washday-mvp-reports`; mode migration/propagation: `washday-mvp-sync`; hosting: `washday-mvp-cloud-release`.

## Verification notes
Exercise every editor against actual staff screens (not just form-save tests), including archive history and immutable prices. Use a second shop/owner and direct URL/POST attempts. Test staff PIN reset/deactivation, code replacement/revocation, denied stage/category/machine removal and bad settings values. Compare prototype owner tabs/screens at 390/1280 px light/dark and 360 px. Use Google test configuration locally, then real allow-list/HTTPS sign-in before release.

## Open questions/blockers
Blocked by `washday-mvp-people` evidence. Custom category/stage mapping with multiple/no matching stages inherits the draft blocker in machines, affecting AC-07/AC-08 integration. Opening time and immediate-predecessor eligibility are approved clarifications, not unresolved proposals.
