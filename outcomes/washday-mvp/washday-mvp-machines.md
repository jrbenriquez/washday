# Record machine use and coordinate it with job stages

## Title and ID
`washday-mvp-machines` — Loads, stage pickers and self-service (milestone 2).

## Source
[PRD](../../reference/docs/PRD.md) §§3–5 Machines and stage routes/models/screens; §6 Job stages, Machines, Simple mode; §§7–8; §9 milestone 2/checklist lines 516–518, 525–526, 531. Owner clarification D-02 in [index](README.md#owner-clarifications).

## References
[Preview](../../reference/prototype/index.html): Machines grid/start/unload/self-service, board machine picker; `machinePicker`, `machinesView`, `tile`, `machineTap`, `selfService`. Visual authority; eligibility follows PRD + D-02, not preview line 1188's broad earlier-stage filter. [Logo](../../reference/img/logo-header.png), [package authority](../../reference/README.md), [shared constraints](README.md#shared-execution-constraints).

## Desired outcome
Staff record loads and unloading as they handle laundry, see true time in use and check flags, and have job stages change consistently whether a load starts from the board or the machine grid.

## Dependencies
`washday-mvp-history`: counter milestone is complete with observable events and timeline. Reuse its jobs and stage contracts. Supply ledger side effects are a later integration, not a prerequisite (see Out of scope).

## Acceptance criteria
- **AC-01:** Branch machine grid groups by category/order and refreshes every 20 seconds. Idle, in-use with job/self-service and elapsed duration, out-of-service, and flagged “check it” states are textual. Flag at `elapsed >= check_after_min` (initial 90). There is no countdown or estimated completion. Porthole rings match preview idle/royal-blue/amber presentation.
- **AC-02:** Only an idle, available branch machine starts a load; competing requests cannot produce more than one open Load per machine. A busy machine shows its current job/stage and cannot offer a new start (D-05). Foreign branch/shop machines/jobs cannot be submitted. End sets `ended_at` and displays “Unloaded after N min”; repeated unload is refused without duplicate effects.
- **AC-03:** Default washer choices are Received/Washing jobs; default dryer choices Washing/Drying. Per approved D-02, a custom category's linked stage accepts jobs in that stage or the immediately preceding active configured stage, not earlier/later. Starting a job from an earlier eligible stage moves it to the linked stage and records the machine cause.
- **AC-04:** Advancing into a machine-demanding stage opens a branch picker limited to its category, or all categories when configured as any. Busy and out-of-service machines are shown disabled. Choosing one is the same server behavior as a grid start: create Load, stage transition with “in W3”, and the category's wash-supply deduction integration. A skipped picker needs a nonblank reason and logs “no machine recorded · reason”.
- **AC-05:** Normal departure from a stage ends that job's open load and frees the previous machine; choosing the next machine is atomic with departure/start. Manual override keeps the load running as specified by progression. Unloading the last load in a move-on stage advances to the next stage unless that next stage also asks for a machine. No accidental second stage advance or supply deduction occurs.
- **AC-06:** Self-service is hidden without an active per-load service. Otherwise staff choose such a service and pay Cash/GCash at start; Load retains charged amount/method and records a collection Event without a Job. Later price edits do not change that collection. Loads today counts starts since Manila midnight; history/timeline show loads, unload durations, automatic stages and self-service collections.
- **AC-07:** Simple mode exposes no Machines screen/picker/loads; paper entries do not generate loads at any branch. Full-mode stale job forms are refused according to the progression contract, even if a machine became unavailable between render and submit.
- **AC-08:** pytest covers stage/load state and stale/concurrent failures; the default New job → washer → unload → dryer → unload → Ready → Claim flow passes Cypress as this behavior integrates. UI meets shared responsive/theme/accessibility/local-asset constraints. Category supply deductions must pass with the ledger in `washday-mvp-supplies` before milestone 2 passes.

## Constraints
[Shared constraints](README.md#shared-execution-constraints). Use core Machine/MachineCategory/JobStage and machines Load boundaries; server is the sole authority. Defaults Washer W (uses wash supplies) and Dryer D; no preloaded self-service service. Category/stage administration is `washday-mvp-settings`, but fixtures may express configuration now.

## Out of scope
Stock ledger implementation: `washday-mvp-supplies`; owner category/machine editor: `washday-mvp-settings`; owner flags/chart: `washday-mvp-monitoring`; device actor/PIN/Undo: `washday-mvp-people`.

## Verification notes
Fixtures: default flow, Steam press linked to Pressing with immediate predecessor Drying, any-category picker, busy/out-of-service/archived machines, simultaneous starts, multi-load last-unload, next-stage-asks-machine, manual override with running load, paper/simple jobs, self-service hidden/active. Inspect Event chronology and state together; run required pytest and Cypress. Test at check-time boundary and Manila midnight. Later owner configuration changes must rerun these tests.

## Open questions/blockers
Blocked by `washday-mvp-history` evidence. D-02 resolves custom eligibility for a category linked to one stage. The PRD permits categories matching multiple stages or an any-category stage but does not define Machines-screen linked-stage selection when several match, or when none matches. **Draft AC-03 for those configurations:** owner must choose a mapping rule; default and single-linked-category behavior is specified and can be developed meanwhile. Do not silently adopt the preview's first-match fallback as a functional requirement.
