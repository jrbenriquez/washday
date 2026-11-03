---
name: orchestrate-work
description: Discover, execute, and resume a software outcome or outcome group through bounded implementation, independent verification, and recalibration until complete or blocked.
---

# Orchestrate Work

## Required references
Read [Handoff contracts](references/HANDOFFS.md) for phase result formats and
[Outcome state](references/WORK-STATE.md) for the persistent schema, transition
table, attempt accounting, stopping conditions, and resume rules. The state
policy gates handoff recommendations; a recommendation cannot bypass a limit.
Read [Group orchestration](references/GROUP-ORCHESTRATION.md) for input resolution,
discovery, scheduling, group checkpoints, branches, execution defaults and
concurrency. Apply its local execution and evidence rules to single outcomes too.

## Inputs
- A single outcome, group directory/index, explicit set, contextual executable
  outcome, or saved state path. With no scope, discover under `outcomes/` and ask
  which to execute, even for one candidate. Never invent work if none exists.
- Existing project-owned outcome state and referenced handoffs/evidence, if any.
- Maximum implementation attempts, default 3 for a new outcome.
- Optional project capabilities registry at `.agents/capabilities/CAPABILITIES.md`.

## Procedure
1. Resolve scope from authoritative documents, repository instructions and accepted
   decisions. Read full outcomes and dependencies; validate identities and the
   graph. Preserve criteria; resolve material ambiguity without inventing a spec.
   Do not silently add external prerequisites to the assignment.
2. Inspect default/current branches, dirty work, and saved work identity. Establish
   or recover the group branch and durable checkpoint per the group reference.
3. Validate or initialize project-owned per-outcome state using the state reference.
   Check outcome identity, workspace, evidence freshness, and saved progress before
   choosing an action. Missing or invalid history never resets the attempt budget.
4. Select eligible work from current evidence, honoring explicit user order and
   otherwise dependencies with suggested order as a tie-breaker. Resume the saved
   invocation or consume its completed handoff when safe.
   Continue from the next unfinished step; block if recovery cannot be justified.
5. For new implementation, select unmet criteria or a cohesive group, enforce
   the saved attempt limit, and persist the increment before invoking `implement`.
6. Save and validate each handoff, then checkpoint its consumption and next
   action. Use independent `verify` results for criterion verdicts. Reconsider
   prior passes when subsequent changes could invalidate their evidence.
7. Route FAIL or INCONCLUSIVE verification through `recalibrate` before another
   implementation. Follow its scoped adjustment or diagnostic action subject to
   the state rules, budget, and no-progress stopping condition.
8. Mark the affected outcome `blocked` for exhausted attempts requiring more
   implementation, unresolved impediments, conflicting requirements, or unsafe recovery. Save
   concrete blockers and the action or human decision needed to resume.
9. After completion or blocking, continue other eligible outcomes automatically.
   Assess later changes against earlier evidence and drain necessary regressions.
   Finish only when all selected criteria have current evidence-backed PASS or no
   remaining work can proceed. Preserve prerequisite waits separately from blockers.
10. Checkpoint and report completed outcomes, blockers/waits, actual checks and
    evidence links, verification limitations, branch/worktree, and application run
    instructions when applicable. Revalidate completion on resume.

## Guardrails
- Keep runtime state and artifacts in the consuming project, suggested
  `.agents/work/<outcome-id>/`, outside reusable skills and capability definitions.
- Never silently change acceptance criteria, reset attempts, or raise the budget.
- Preserve unrelated changes and previously working behavior.
- Default to local development, labelled fixtures and captured external effects
  where criteria permit. Real external effects require explicit authorization.
  Check verification capabilities early; unavailable or unrun checks cannot PASS.
- Single-agent execution is the baseline. One orchestrator owns state writes;
  parallel work requires authorization, supported isolation and the group policy.
