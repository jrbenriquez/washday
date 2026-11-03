# Ivan & Ivy Laundry — vision brief

28 Oct 2026 · JR

> This is the agreed vision. Where it differs from `PRD.md`, the PRD is newer and wins. In particular, the PRD settles hosting, hub hardware and owner sign-in.

## What it is and for whom

A tablet-first system that runs a multi-branch drop-off laundry business, and keeps every branch working with no internet. Staff record their normal actions (taking a job, starting a machine, releasing laundry). The app turns those taps into a complete picture of loads, sales and supplies for the owner.

- **Owner:** checks all branches from her own phone or tablet, mostly online. Today she uses a logbook, and Excel only for BIR reports.
- **Staff:** about 2 per branch. Busy, standing, often with wet hands.
- **Business:** 3 branches with 5–10 washers and dryers each. Mostly drop-off (wash-dry-fold); self-service exists but is rare.
- **Payments:** cash and GCash.

## Core jobs

1. **Take a drop-off job in under 30 seconds:** weight in kilos, service, add-ons and optional customer, then a job number with a digital and printable claim stub.
2. **Run machines with one tap:** tap a washer or dryer tile to start a load for a job, and tap it again to finish. This records loads per machine and how long each machine is busy or idle.
3. **Move each job forward one step per tap:** Received → Washing → Drying → Folding → Ready → Claimed. Paid or unpaid, and cash or GCash, are recorded when the job is claimed.
4. **Track supplies without separate logging:** every load deducts supplies automatically. Staff do a quick count at closing, and any mismatch is flagged.
5. **Give the owner one view of every branch:** daily loads per machine, sales by cash and GCash, low stock, unclaimed jobs, and a BIR-ready Excel export.

## Version 1 scope

- Drop-off jobs priced **per kilo by default**, with per-load pricing available as a service setting
- Minimum kilo for clothes, add-ons, a rush fee, and fixed-price piece items by size (for example a Queen comforter), with no weight needed for a pieces-only job
- Self-service loads as a simple option (expected to be rarely used)
- Machine board per branch: one tap to load and one to unload. It shows time in use and flags machines in use longer than a set time (default 90 min)
- Job stage flow, plus payment (cash or GCash) recorded at claim
- Jobs list (including released jobs) and a day history with date filter and search; each job opens a timeline from receiving to release
- Services, add-ons, piece items and fees all editable by the owner
- Customer records (name and phone), optional on each job
- Digital claim stub, printable through the tablet's print dialog
- Supply types managed by the owner (add, archive, low level, amount per washer load or packed job). Staff can request new ones, and the owner can unlock adding for staff
- Stock per branch with supplies bought centrally: "receive" entries, end-of-day count with variance flags, low-stock alerts
- PIN for payments and claims on shared devices, switched on or off by the owner. Staff phones sign in per person
- Owner dashboard across all branches, a watch-only live view of each branch's machines and job board, and a BIR export to Excel
- Owner settings: branches, machines and categories, staff, job stages, fees, services, add-ons, piece items and supplies, all editable
- Simple mode per branch for onboarding (a short board such as Received → Ready, no machines)
- Light theme by default, with a dark theme switch saved per device

**Later:**
- SMS when a job is ready
- Issuing official receipts (OR)
- Direct Bluetooth thermal printing
- Loyalty or promos
- Machine maintenance logs
- Phase 2, only if stage tapping proves slow: physical job tags (NFC stickers or e-ink Bluetooth tags), piloted at one branch

## Look, feel and devices

The app should feel like a sturdy counter tool: large tiles, high contrast and almost no typing.

- **Feel:** clean and fresh, with a crisp light theme. Machine tiles show state by colour and time in use, so staff can read the board from a step away.
- **Entry style:** tap first. Number pads for kilos and chips for services and add-ons; free text only for notes. Touch targets are 56 px or larger.
- **Feedback:** every action shows a toast with Undo.
- **Counter tablet (one per branch):** taking in jobs, claims and payment, and the supplies count.
- **Staff phones (one per staff member):** worn on an armband or lanyard in a waterproof pouch. Mainly for Machines and moving jobs to Ready.
- **Owner:** her own phone or tablet. The dashboard filters by branch.
- **Brand:** Ivan & Ivy Laundry ("Quick Clean", est. 2020). Colours come from the logo: royal blue, teal, sky blue, white and bubble grey. The hexagon badge logo appears in the app header.

## Stack and sync

Each branch runs its own small Django server (the branch hub) on the shop's local Wi-Fi, so the branch keeps working with no internet. The cloud is only for the owner's view and for backup.

```
 ┌────────────── each branch (works with no internet) ─────────────┐
 │  Counter tablet ┐                                               │
 │  Staff phones   ┴─ local Wi-Fi ─▶  Branch hub (Django + HTMX,    │──▶ events up when online ──▶  Cloud server ──▶ Owner dashboard
 │                                    event log; router+hub on UPS)│◀── prices, settings down ◀──  (Django, Postgres)
 └─────────────────────────────────────────────────────────────────┘
```

Phones and tablets load plain Django + HTMX pages from the hub, so every device in a branch sees each change within seconds.
- The hub records events and sends them to the cloud whenever the internet is up, and receives prices and settings back.
- Each branch writes only its own events, so branches never conflict.
- Inside a branch, a tap that is already out of date is refused, and staff are told why.
- If a hub fails, the branch uses a paper job sheet until a spare hub is swapped in. The new hub rebuilds from the cloud.

## Decisions

| Topic | Decision |
| --- | --- |
| Naming | "Job" everywhere (not order or ticket); claim stub for the customer's slip |
| Service mix | Drop-off first; self-service kept as a rarely used option |
| Pricing | Per kilo by default; per-load available per service |
| Job extras | Minimum kilo, add-ons, rush fee; piece items at a fixed price per size, editable by the owner, never weighed |
| Machines | Track time in use only, with no countdown; flag after a set time |
| Supplies | Bought centrally, stock per branch; owner manages types and archives rather than deletes |
| Customers | Records exist; attaching one to a job is optional |
| Claim stub | Digital plus printable; official receipts later |
| BIR | Excel export, matching her current process |
| Payments | Cash and GCash |
| Staff PIN | For payments and claims on shared devices; switched on or off by the owner |
| Devices | Counter tablet plus one phone per staff member in each branch; owner on her own device |
| Device setup | Owner adds each device by QR code as shared or personal; devices without a key can't open the app |
| Staff sign-in | Personal phones: name and PIN once per shift, with automatic sign-out at closing. Counter tablet: no sign-in, PIN on claims and payments |
| Start screens | Staff phones open on Machines; the counter tablet opens on New job |
| Offline | Branch hub on local Wi-Fi with a UPS; the branch runs fully without internet |
| Stack | H1: Django + HTMX on each branch hub and in the cloud; no React |
| Owner live view | Watch-only machine grid and job board for each branch |
| Theme | Light by default; dark switch per device |
