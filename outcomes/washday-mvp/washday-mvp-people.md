# Enrol devices, attribute staff actions and undo recent mistakes

## Title and ID
`washday-mvp-people` — Enrolment, shift/PIN policies and compensating Undo (milestone 3).

## Source
[PRD](../../reference/docs/PRD.md) §§3–5 device/shift/staff routes/models/screens; §6 People and devices, Job stages/Undo, Paper job sheet PIN rules; §§7–8; §9 milestone 3/checklist lines 530, 536–541.

## References
[Preview](../../reference/prototype/index.html): visual language, `withPin`, modal/PIN pad and toast; its per-action blanket PIN and snapshot undo are disposable. Setup/shift screens are specified in PRD, not fully previewed. [Package README mapping](../../reference/README.md), [logo](../../reference/img/logo-header.png), [shared constraints](README.md#shared-execution-constraints).

## Desired outcome
Only enrolled branch devices can work; personal devices attribute actions to a shift, shared devices follow owner-selected PIN rules, and a recent reversible mistake is corrected by a new event rather than erasing history.

## Dependencies
`washday-mvp-supplies`: complete staff behaviors, Event/ledger invariants and test fixtures exist. Owner-facing staff/device management is milestone 4; use explicit development fixtures for provisioning here, not a public unauthenticated administration flow.

## Acceptance criteria
- **AC-01:** `/device/start/` provides branch/logo and brief Android/iOS Add to Home Screen steps; scanning QR or visiting this page saves no device key. The home-screen app opens setup, accepts a **6-digit** code for its branch/address, saves a long-lived key cookie only then and redirects to the enrolled start flow. Closing/reopening retains enrolment.
- **AC-02:** Codes expire after **15 minutes**, work once, and each device has at most one unused code. Expired, used and wrong-branch codes fail; five wrong submissions lock the code box for **1 minute**. Key/code/PIN storage is hashed, with no plaintext secret in persistent records/event payloads.
- **AC-03:** Missing, invalid or revoked staff keys cannot open protected pages/actions and go to setup; revocation takes effect immediately on subsequent requests. Lost key displays “This device isn't set up”; a new code restores access without re-scanning if the icon remains. Public install/setup and owner authentication endpoints retain their necessary independent access boundaries.
- **AC-04:** Shared devices start at New job and have no Shift. Personal devices first show branch staff and Who's working, require name + **4-digit** PIN, and allow exactly one open Shift per device. Actions record that shift's staff member; End shift or branch closing time closes it and requires sign-in again. Full-mode personal default is Machines; simple-mode personal devices open Jobs after sign-in (approved D-04).
- **AC-05:** Shared PIN master/action policies are honored server-side: default claim/payment and manual override on; create, count, receive and add-type off. Selected actions record the matched active branch staff; unprompted actions record the device. Paper create/claim obey the corresponding rules. Personal actions use the signed-in shift rather than repeated per-action PIN prompts. PIN pad locks **1 minute after 5 wrong tries**.
- **AC-06:** Undo from the device that made the action works within **6 seconds** on the last reversible action, and refuses after the window, from another device or when no longer safely applicable. It appends a compensating Event and restores the reversible state/ledger/payment effect without deleting/editing original Events or immutable StockCounts; the timeline shows correction and financial summaries do not double count. Repeating Undo cannot compensate twice.
- **AC-07:** Device branch is fixed by enrolment, not a staff branch dropdown. Header shows logo, branch, connection to the serving hub/cloud, theme, signed-in staff on personal devices and End shift. Hub staff never see cloud sync status or an offline simulator.
- **AC-08:** All existing staff routes/actions are guarded, branch/shop isolated, and actor attribution survives history reads and compensation. pytest covers code expiry/single use/lockout/wrong branch, invalid/revoked keys, PIN/shift policies and Undo boundaries. Responsive/theme/accessibility and locally served assets apply to setup, shift, PIN and toast.

## Constraints
[Shared constraints](README.md#shared-execution-constraints). No sign-up or browser database. Enrolment must account for separate Safari/home-screen storage; never save the key from QR. Mode changes require new enrolment, integrated by sync. Security defaults must be in place before direct pilot. Undo cannot be implemented by the prototype's full-state snapshot restore.

## Out of scope
Owner Google access, staff create/reset/reactivate and Devices UI: `washday-mvp-settings`; actual iPad/iPhone/Android installation persistence checks: `washday-mvp-cloud-release`; hub-side settings/key propagation: `washday-mvp-sync`.

## Verification notes
Use clock-controlled boundary tests, wrong-branch codes, replacement codes, two personal/shared sessions, inactive staff, closing-time rollover and Undo at either side of 6 seconds. Regress every prior write path with PIN policies on/off, including self-service collections, stock counts and paper workflows. Record which actions are reversible and evidence for refusing unsafe compensation; immutable count records remain intact. Physical home-screen/browser-storage behavior requires device evidence later, not merely a simulated cookie test.

## Open questions/blockers
Blocked by `washday-mvp-supplies` evidence. None otherwise; D-04 resolves the simple-mode personal start screen.
