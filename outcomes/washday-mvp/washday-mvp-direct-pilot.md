# Prove direct + simple mode in a two-week branch pilot

## Title and ID
`washday-mvp-direct-pilot` — Initial live pilot gate (rollout step 2).

## Source
[PRD](../../reference/docs/PRD.md) §1 Success criteria; §9 rollout steps 1–3, still-to-collect; §10 devices/network/cloud/paper setup. D-01 branch opening time in [index](README.md#owner-clarifications).

## References
[Package README](../../reference/README.md), [preview](../../reference/prototype/index.html) for JR's usability review, [paper sheet](../../reference/docs/paper-job-sheet.pdf) for outages, [brand](../../reference/img/logo-header.png), [shared constraints](README.md#shared-execution-constraints).

## Desired outcome
A real branch operates direct + simple for two weeks with staff trained, real configuration and measured success, providing the source-required gate before laptop-hub work.

## Dependencies
`washday-mvp-cloud-release`: production direct mode and acceptance evidence. External: owner's real services/prices/add-ons/fees/pieces, supplies/usage/thresholds, branch names/codes/opening and closing times, staff/devices, BIR sample, branch consent/schedule and two weeks' live operation. These are not build blockers for earlier specified software.

## Acceptance criteria
- **AC-01:** Pilot branch uses Direct + Simple; real catalog/supply values, branch names/hours and owner account are entered through settings, counter/phones enrolled, staff trained with onboarding instructions and printed paper sheets available. No placeholder customers/staff/prices are treated as real.
- **AC-02:** After a **2-week** pilot, median first New job tap → job created is **30 seconds or less**, measured from actual timestamps. Measurement captures first tap as well as creation, not only server execution latency; record how it excludes test/demo jobs and handles abandoned intake.
- **AC-03:** Full stock count at the pilot branch is saved on **at least 6 of 7 days**, with count events and dates as evidence across the pilot. Other branches' equivalent target remains owned by rollout; a one-branch pilot cannot prove all-branch attainment.
- **AC-04:** Every job written on paper during a direct-mode outage is entered **within one working day of internet returning**, preserving sheet P number and occurrence/payment/claim times; reconcile all paper rows to app jobs/claims. Record return-of-internet and actual working-day context. Use an observed or arranged outage drill if no natural outage occurs, retaining the sheet evidence.
- **AC-05:** Online events are shown on owner dashboard **within 1 minute**, and sales/history/BIR totals reconcile to actual jobs and collections. Staff/owner/JR review captures direct-mode success evidence; the ≥90% linked washer/dryer target is explicitly inapplicable to this simple-mode pilot, not waived for later full mode.

## Constraints
[Shared constraints](README.md#shared-execution-constraints); source rollout timing and exact thresholds are preserved. This is an observed operational outcome, not a request for an agent to invent two weeks of results or buy devices. Timestamp instrumentation needed for success measurement belongs with the related flow; no new analytics platform is required.

## Out of scope
Hub outage/UPS/full-mode load targets and remaining branches: sync/hardware/hub-rollout owners. Generic software fixes discovered in pilot require bounded changes and regressions of the owning earlier outcome.

## Verification notes
Collect the two-week event dataset, intake-start measurements, full-count calendar, paper sheets/entry mapping, collection reconciliation and JR/owner review. Use real local working days for outage recovery, not an invented 24-hour equivalence. An automated fixture cannot prove live-pilot criteria.

## Open questions/blockers
Blocked by cloud release, real operating inputs/devices/training and two weeks of observed evidence. Owner must supply working-day context for AC-04 if not clear from actual branch schedule. No success metric is marked passed by this plan.
