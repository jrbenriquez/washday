# Accepted machine-start flow — 3 November 2026

Authority: user instructions during orchestrate-work, after initial Q-01 answer.

The user initially chose an eligible-stage picker for multiple matching stages, with self-service only for no matching stage (Q-01). They then clarified that the staff Machines page is primarily monitoring, that starting work there is highly discouraged, and that anything doable from the Jobs board should be done on the Jobs board.

Accepted execution interpretation: job-linked machine starts are offered on the Jobs board's next-stage machine picker. The staff Machines page shows machine state/current job/stage/elapsed time/check flags and Unload, and only offers paid self-service starts for loads without a Job. It never creates a Job or offers job-linked starts. Board stage target is explicit, including any-category stages. A category's multiple/no-linked-stage mapping no longer requires implicit grid target selection; the initial Q-01 chooser applies only if a later explicitly approved flow reintroduces a Machines-screen job start.

This is an explicit behavior amendment to the original grid-start descriptions in PRD §6 and machines AC-03/04, settings AC-07/08 and sync AC-06 regressions. Original source documents and criterion IDs are retained. Verify those criteria against this accepted amendment and retain default/custom category eligibility and all concurrency, availability, tenancy, stale-action, stage/load, self-service and supply invariants. Unload behavior is unchanged. No existing acceptance verdict is waived.

No permission for production deployment, purchases, external messages or delegation is added. Outcome identities, dependencies and implementation budgets are unchanged.
