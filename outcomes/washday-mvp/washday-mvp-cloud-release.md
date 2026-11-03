# Make direct-mode counter work usable on the production cloud

## Title and ID
`washday-mvp-cloud-release` — Secure direct-mode release and device acceptance (milestones 1–4 integration).

## Source
[PRD](../../reference/docs/PRD.md) §3 cloud stack/direct mode; §§5–8; §9 rollout steps 1–2 and checklist; §10 cloud/devices/paper setup. All earlier behavior owners remain primary owners; this outcome verifies their assembled direct-mode release.

## References
[Package README](../../reference/README.md), [preview](../../reference/prototype/index.html): staff/owner screens at 390/1280 px and both themes; [paper sheet](../../reference/docs/paper-job-sheet.pdf): A4 landscape 100%, two A5 copies; [logo](../../reference/img/logo-header.png), [shared constraints](README.md#shared-execution-constraints).

## Desired outcome
The production cloud safely serves direct branches on supported staff devices and the owner's phone, with backups and reproducible acceptance evidence before a branch depends on it.

## Dependencies
`washday-mvp-reports`: all counter/machine/supply/people/owner functionality and exact BIR format verified. External: VPS/domain/HTTPS access, Google OAuth configuration and owner allow-list, current Android/iPad/iPhone devices, shop network and mobile data, JR's milestone review. Infrastructure access is not assumed granted by a planning document.

## Acceptance criteria
- **AC-01:** Cloud uses the prescribed Docker app with PostgreSQL, HTTPS-only public service, actual Shop/ShopOwner binding and protected staff routes. Direct-mode writes commit state+Event atomically without requiring a hub/outbox; production has exactly one real Shop (second shop only in test environment) and no sample operational data/reset controls.
- **AC-02:** All milestones 1–4 checklist items have actual test/review evidence against their primary outcomes, with JR review against prototype. Required pytest suites pass on the cloud database; Cypress covers job lifecycle, count and paper-sheet intake/release. Direct + simple and full-mode regressions include stale sessions, stock, PINs, Undo and exports.
- **AC-03:** On current Android Chrome tablet (10-inch or larger) and phone, direct-mode staff flows pass. On current Safari iPad and iPhone, QR → Add to Home Screen → open icon → setup code persists after reopening; invalid/revoked/lost-key recovery works. iPad New job → Claim passes and stub supports AirPrint or digital display. Record actual device/browser versions, not just viewport emulation.
- **AC-04:** Direct staff pages respond in **under 1 second on shop internet**; dashboard **under 2 seconds on mobile data** and online owner event visibility **within 1 minute**. Capture environment, representative fixtures, measured timings and repeatable procedure; local laptop timings cannot stand in for these network checks.
- **AC-05:** Every screen meets 360 px minimum support and prototype comparison at **390 px / 1280 px in light/dark**. Typography, brand, job tags, machine portholes, stub, navigation, no page overflow, ≥44 px targets/56 px primary controls, labels/focus and textual status meet shared constraints. Unpreviewed screens follow the same system and PRD behavior.
- **AC-06:** Daily cloud PostgreSQL backups retain **30**; a recovery exercise restores expected data without leaking another test shop through the app or a per-shop restore. Restore evidence distinguishes a whole operator backup from a shop-scoped export. Immutable events survive recovery.
- **AC-07:** With direct branch internet unavailable, staff use the supplied paper sheet; restored service accepts the sheet's jobs/releases with original times, P references and duplicate detection, and reports reconcile. No browser offline database/service-worker sync is introduced. Provide onboarding steps covering shared/personal devices, claims, counts, outages and paper entry; print/inspect the source sheet at A4 landscape 100%.

## Constraints
[Shared constraints](README.md#shared-execution-constraints). Preserve rollout: direct + simple pilot before hub hardware and milestone 5. Packaging the cloud now does not force hub sync implementation early. Source hosting target is a small Singapore VPS (~1 vCPU/2 GB example); actual provision/access is external. No hardware purchases are authorised by this plan.

## Out of scope
Two-week business acceptance: `washday-mvp-direct-pilot`; hub split/outbox/mode migration: `washday-mvp-sync`; hub backups/update/recovery: `washday-mvp-hub-operations`; N100/UPS checks: `washday-mvp-hardware`.

## Verification notes
Run the app's documented pytest/Cypress and production-like PostgreSQL checks; collect devices, screenshots, timing records, backup/restore logs and signed JR review. Use a second isolated test shop to probe routes, queries, exports and recovery; never seed it into the one-shop production dataset. PDF has generic branding and example row: keep examples identified as examples and confirm pilot print suitability. All hardware/network/review claims remain unrun until explicitly performed.

## Open questions/blockers
Blocked by `washday-mvp-reports` evidence and external hosting/OAuth/device/network access/JR review. Fonts are not included in package; offline/local-asset acceptance requires acquired self-hosted binaries. Paper-sheet generic brand/sample row must be reviewed before live training; do not edit the source asset silently.
