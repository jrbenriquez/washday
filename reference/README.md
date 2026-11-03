# Ivan & Ivy Laundry — reference package

Ivan & Ivy Laundry runs three drop-off laundry branches in the Philippines. This package describes version 1 of its management system:
- a cloud app where the owner watches all branches and manages settings, and which serves staff screens for branches in direct mode (the default for a new branch)
- an optional branch hub at each shop serving a counter tablet and staff phones over local Wi-Fi, so service never depends on the internet (hub mode)

The package is the starting point for building it.

## Start here
1. Read `docs/PRD.md`. It covers what to build, the stack, data model, rules, sync protocol, acceptance criteria, hardware and setup.
2. Open `prototype/index.html` at 390 px and 1280 px. It is the source of truth for look and interaction. Try both views ("Staff tablet" and "Owner") and both themes.
3. Use `docs/brief.md` to decide unclear design choices.

When the PRD and the prototype disagree, the PRD wins on behaviour and data, and the prototype wins on look and feel.

## Ground rules
- **Stack:** server-rendered Django 6 + HTMX on Python 3.13, with one codebase running as `APP_ROLE=hub` or `APP_ROLE=cloud`. Use DRF only for the sync endpoints, SQLite on hubs and PostgreSQL in the cloud.
  - Don't add React, a bundler, a client-side database or service-worker sync.
  - Don't add any new framework or dependency without approval.
- **Data:** every write also appends an Event in the same transaction. Events are never edited or deleted, and all keys are UUIDs.
- **Tenancy:** the cloud is one multi-tenant app. A Shop sits above Branch, and every shop-owned row is scoped by `shop` through the tenant-scoped base model (PRD sections 3 and 4). Version 1 has one shop, but never write a query that could return another shop's data. Don't build sign-up, billing or plans.
- **Placeholders:** sample data, sample prices, `[Branch 1–3]`, `[Customer A]` and `[Staff 1]` are not real data. Don't ship them or invent values for them; the owner's real values go in through Settings.
- **Words:** use "job" in all UI copy (never "order" or "ticket") and "claim stub" for the customer's slip.
- **Offline assets:** fonts, icons and the logo must be served by the hub.
- **Later work:** PRD section 11 lists what is planned for version 1.1 (thermal stub printing). Don't build it in version 1.

## How the prototype maps to the real app

| Prototype | Real app |
| --- | --- |
| The `S` state object kept in `localStorage` | Django models (PRD section 4) on the hub or cloud, mirrored to the cloud by events in hub mode |
| `seed()` sample data | A `seed_demo` management command for development only |
| `priceLines()`, `NEXT`, `machineState()`, `deduct()` | Server rules in PRD section 6; pricing and stage changes live in `jobs`, deductions in `supplies` |
| `emit()` plus the sync pill and its offline toggle | Event outbox and `/sync/push/`; staff see only a connection status |
| `withPin()` PIN pad on every key action | PIN only on shared devices for owner-chosen actions; personal devices use the shift sign-in |
| `act()` with an Undo toast | `/undo/<event_id>/`, writing a compensating event within 6 seconds |
| Branch dropdown in the header | Fixed by the device's enrolment; a device belongs to one branch |
| "Staff tablet" / "Owner" switch | Staff screens (hub, or cloud in direct mode) and owner screens (cloud) |
| Owner "Live branches" tab | `/owner/live/<branch>/`, read-only, reusing the staff card and tile partials |
| Theme button and Dark theme setting | `data-app-theme` on `<html>`, saved per device in a cookie |
| 20-second `setInterval` refresh | `hx-trigger="every 20s"` on the board and machine grid |

## Files
- `docs/PRD.md`: requirements, rules, hardware list and setup
- `docs/brief.md`: the agreed vision and decisions
- `docs/paper-job-sheet.pdf`: the printed A4 job sheet staff use during outages (PRD section 6)
- `prototype/index.html`: clickable prototype, self-contained. It uses a generic placeholder brand, "Bula & Banlaw Laundry", with an SVG badge in the same design and colours; the real app shows Ivan & Ivy Laundry's name and logo
- `img/logo-original.jpg`: the full-size brand logo
- `img/logo-header.png`: a small crop of the real logo, for the real app's header

## Notes
- The fonts are Saira Condensed (headings), Figtree (body) and JetBrains Mono (numbers). The prototype loads them from Google Fonts; the real app must self-host them.
- Use Philippine pesos with 2 decimal places, kilograms with 1 decimal place, and the Asia/Manila time zone for "today".
- Machines show only time in use. Never add countdowns or estimated finish times, because the shop can't measure them.
- Two deployment modes share one codebase: direct mode (staff screens served by the cloud; the default for a new branch, together with simple mode) and hub mode (served by the branch hub). See "Deployment modes" in PRD section 3. Every staff flow must pass in both.
- Devices: Android in both modes; iPad and iPhone Safari are also supported in direct mode, where claim stubs print through AirPrint or stay digital.
- Device enrolment: the QR code only opens the "Add to Home Screen" page; the device key is saved when staff type the 6-digit setup code inside the home-screen app, because iPad and iPhone home-screen apps don't share the browser's storage. Never save the key from the QR link itself (PRD section 6, People and devices).
- Paper entries keep the times written on the sheet (`received_at`, `paid_at`, `claimed_at`); totals and reports must use those, not `created_at` (PRD section 6, Paper job sheet).
- Build in the order of the rollout plan (PRD section 9). Branches go live in direct + simple mode after milestone 4; milestone 5 runs on JR's laptop as the hub before the real N100 hub is checked.
- Before the pilot, collect real prices, supply amounts, branch names, closing times, and a sample of the owner's BIR Excel sheet (PRD section 9).
