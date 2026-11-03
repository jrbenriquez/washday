# Prove hub/full mode and complete the three-branch rollout

## Title and ID
`washday-mvp-hub-rollout` — Live hub pilot, remaining branches and spare (rollout steps 6–7).

## Source
[PRD](../../reference/docs/PRD.md) §1 Success criteria; §3 mode transitions; §8 whole-system targets; §9 rollout steps 6–7/checklist; §10 branch/spare setup. This is final observed integration, not deferred ownership of ordinary feature tests.

## References
[Package README](../../reference/README.md), [preview](../../reference/prototype/index.html) reference presentation, [paper sheet](../../reference/docs/paper-job-sheet.pdf) counter fallback kit, [brand](../../reference/img/logo-header.png), [shared constraints](README.md#shared-execution-constraints).

## Desired outcome
The qualified pilot branch runs hub mode and adopts full mode when staff are ready; all three branches and a tested spare are operational with evidence that the assembled system meets the original business targets.

## Dependencies
`washday-mvp-hardware`: qualified N100 kit and all prior outcomes, including successful direct pilot. External: after-closing migration window, trained staff/owner approval, production configuration/devices/network for all branches, additional hub kits and spare, **2-week hub pilot** and live event data.

## Acceptance criteria
- **AC-01:** Pilot moves direct → hub after closing by bootstrap/mode switch/device re-enrolment; no lost/duplicated events or two active writers. Simple mode is disabled when staff are ready, without losing jobs or bypassing PINs. Reverse migration is demonstrated using the drained-outbox protocol in a suitable controlled environment.
- **AC-02:** After **2 weeks in hub mode**, median first New job tap → creation is **≤30 seconds**; at full-mode branches **at least 90% of claimed jobs have a linked washer and dryer load**. Use actual events and documented pilot intervals, excluding explicitly marked demo data, not invented or hand-filled measurements.
- **AC-03:** Full stock count is saved at **every branch on at least 6 of 7 days**; count freshness/history agrees. Simple branches remain subject to stock targets even though their washer-load link target is inapplicable until full mode.
- **AC-04:** Hub **4-hour internet outage** causes no visible staff change and loses no events; owner's online event visibility is **within 1 minute** after normal connectivity. Retain source-required router-cut evidence, confirm pilot equipment/configuration matches qualified behavior, and regress previous synced totals, stock, history/BIR and cross-shop isolation after live integration changes.
- **AC-05:** Any direct-mode outages during remaining rollout have every paper job encoded **within one working day of internet returning**, preserving sheet times/P numbers; hub-failure fallback/recovery and spare restore procedure remain usable and scoped, **under 30 minutes** for synced branch recovery.
- **AC-06:** Branches 2 and 3 follow the same path: direct first, hubs prepared at home later, shared/personal devices re-enrolled, real branch settings loaded and paper stacks/training available. Both branches are running; spare hub is preinstalled and **tested once**. Remaining procurement follows successful first hub pilot, not an upfront requirement to purchase everything.
- **AC-07:** Final evidence links every required checklist behavior and non-functional target to its primary owner and current regression result; no missing device, multiarch, nightly update, data-safety, accessibility, tenant, paper-time or full-flow acceptance is replaced by historical completion alone. Owner/JR review records actual rollout state and outstanding issues.

## Constraints
[Shared constraints](README.md#shared-execution-constraints); do not broaden version 1 into thermal printing, customer messaging, receipts, sign-up/billing or hardware tags. Staff stay on standard screens; owner live view remains watch-only. This outcome owns rollout observations, not a miscellaneous unimplemented feature backlog.

## Out of scope
All §2 exclusions and §11 version 1.1 remain excluded. New feature requests after pilot require separate assignment; discovered regressions require affected earlier outcomes to be reverified.

## Verification notes
Collect live two-week pilot evidence, percentage numerators/denominators and event links, intake timings, branch count calendar, outage/paper reconciliations, migration Event sets, spare restore timer and owner review. Verify source success thresholds independently of UI badges. Never fabricate elapsed operational evidence or count planned checks as passing.

## Open questions/blockers
Blocked by hardware qualification and external production access/staff schedule/additional devices/hubs/spare, two-week observation and actual all-branch data. No new functional assumption is introduced.
