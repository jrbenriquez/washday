# Take a correctly priced job and issue its claim stub

## Title and ID
`washday-mvp-intake` — Counter intake, including paper intake (milestone 1).

## Source
[PRD](../../reference/docs/PRD.md) §§1–4; §5 New job / Claim stub; §6 Job numbers, Pricing, Paper job sheet; §7; §8; §9 milestone 1 and checklist lines 510, 524, 542, 546. [Package README](../../reference/README.md).

## References
- [Preview](../../reference/prototype/index.html): Staff tablet → New job → claim stub; `counterView`, `summaryHTML`, `showStub`, light/dark `:root` blocks. Visual and interaction authority only.
- [Header logo](../../reference/img/logo-header.png), [original logo](../../reference/img/logo-original.jpg): actual brand assets. Use Shop name/logo, not the preview's generic brand.
- [Paper sheet](../../reference/docs/paper-job-sheet.pdf): Part A fields and reconciliation fixture; example row and “X & Y Laundry” are placeholders.
- [Brief](../../reference/docs/brief.md): subordinate design guidance. [Set constraints and owner clarifications](README.md#shared-execution-constraints).

## Desired outcome
On a laptop development server, staff can record a walk-in or known customer's clothes, pieces, or mixed job, see a server-computed price, choose payment now or at claim, and receive a digital/printable claim stub. Paper intake preserves the original reference and occurrence times.

## Dependencies
None. Repository inspection found only skills, `skills-lock.json`, and the reference archive; no app, manifests, lockfiles, architecture decisions, outcomes, or work state. Introduce the prescribed stack and shared tenancy/event infrastructure with this first observable behavior.

## Acceptance criteria
- **AC-01:** A persisted job can contain positive clothes weight, one or more pieces, or both; zero weight with no pieces is refused without a job, number consumption, or partial write. Active services/add-ons/fees, piece-size steppers, optional customer search/create (name/phone), notes, live price summary and payment choice are available. Customers are shared within the shop, not across shops.
- **AC-02:** For positive kg, per-kg base is `max(kg, min_kg) × price`; per-load base is `max(1, ceil(kg / kg_per_load)) × price`. At 0 kg no service line or minimum charge exists. Pieces use quantity × size price, outside the weight/minimum. Add-ons and selected fees are each added once. Each line uses decimal half-up rounding to 2 decimals and total equals the sum of rounded lines.
- **AC-03:** JobLines snapshot labels, kinds and amounts. Later price/catalog edits do not change an existing job's lines or total. Heavy-items per-kg pricing is supported without treating pieces as weight. Fees are selectable chips; Rush is explicitly seeded at ₱50 with “Same day” per §4, not inferred from other sample prices.
- **AC-04:** Branch numbers start at branch number × 1000 + 1 and increase by 1, unique within the branch even under concurrent intake. UUID keys, Decimal money/weight fields and §4 relationships are preserved. A state write and its immutable Event with UUID and branch sequence commit together or both roll back.
- **AC-05:** Pay-at-claim leaves the job unpaid; Cash/GCash on intake records the amount, method, paid time and actor and exposes “at drop-off” in the event evidence. Optional GCash reference is retained when supplied. Add-on stock deductions are connected by `washday-mvp-supplies`, not silently omitted at release.
- **AC-06:** `?paper=1` / From paper sheet captures P number, sheet date/time received, written total, payment and paid time if paid. Dates today through 7 days back are accepted; future and older dates are refused. `received_at` and job-created `occurred_at` use sheet time, `created_at` uses entry time, and payload identifies `from_paper`. Duplicate (branch, sheet date, P number) warns with the existing job number and opens that job instead of creating another.
- **AC-07:** Paper intake uses entry-time catalog prices, shows app and written totals together when different, and lets staff keep the app total or add an explanation note; it never replaces the computed total with the handwritten total. No loads are invented. The stub shows “Paper P-7” and the paper receipt/entry provenance.
- **AC-08:** The digital stub shows number tag, customer/walk-in, actual received time, service or pieces-only, weight/pieces, lines, total and payment state. Print opens the device's print dialog with a small-slip stylesheet; no thermal integration is present. Android printing and direct-mode Safari/AirPrint/digital evidence is completed in `washday-mvp-cloud-release`.
- **AC-09:** Staff screens use actual brand assets, prototype tokens in `static/css/tokens.css`, light default and cookie-persisted `data-app-theme`, teal punched job tags and perforated/notched stub. At 390/1280 px in both themes and at 360 px, no page-level horizontal overflow occurs; rail becomes bottom navigation below 760 px. Controls are labelled, focus visible, status textual, targets ≥44 px and primary controls ≥56 px; actions give toast feedback. Fonts/icons/logo are locally served.
- **AC-10:** Tenant-scoped default managers and current-shop resolution prevent foreign-shop customers/catalog/jobs from appearing or being referenced; foreign identifiers return 404. A rollback test proves no event/state divergence. A model-scoping regression check fails for a shop-owned model lacking scoping, including future models as they are introduced.

## Constraints
Use Python 3.13, Django 6 templates + HTMX, prescribed Django app boundaries (§3), SQLite for local development; retain compatibility with cloud PostgreSQL and hub SQLite WAL. No React, bundler, client database, service-worker sync or unapproved framework/dependency. Follow [shared constraints](README.md#shared-execution-constraints), including immutable transactional events and English/₱ with 2 decimals/kg with 1 decimal/Asia-Manila. Preview state, browser-local storage, sample prices and reset controls are disposable preview code, not production behavior. `seed_demo` is development-only; never ship example customers/staff/branch names or operational prices. This milestone is local development, not an unauthenticated production release.

## Out of scope
Stage/claim/paper release: `washday-mvp-progression`; event-derived discovery: `washday-mvp-history`; deductions: `washday-mvp-supplies`; authentication/enrolment/Undo: `washday-mvp-people`; owner editing: `washday-mvp-settings`; production/device acceptance: `washday-mvp-cloud-release`; hub replication: `washday-mvp-sync`.

## Verification notes
Use clearly marked test-only shops, branches with different sequences, kg/load services, piece variants, rounding edge cases, absent services for a pieces-only job, payment variants, and paper dates at today/−7/−8/future boundaries. Run pytest pricing, tenancy, concurrency and paper persistence checks; inspect DB/events and reload the stub. Compare screenshots with the referenced preview at both required sizes/themes and 360 px; disable external network requests to prove local assets work. Font binaries are absent from the package; obtain the specified self-hosted fonts during implementation, record their origin, and do not claim offline typography acceptance until exercised. Commands and timing evidence must come from the implemented app; none has been run by this planning task.

## Open questions/blockers
None for local implementation. Real operating values are external prerequisites of the pilot, not permission to invent production values. Font binaries must be acquired for AC-09 verification.
