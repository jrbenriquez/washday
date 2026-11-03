<!-- Generated from docs/GROUP-ORCHESTRATION.md by scripts/sync-handoffs.py. Do not edit this copy. -->

# Outcome-group orchestration

This is execution policy for instruction-based skills, not an executable scheduler.
The coordinator applies it with the consuming project's tools. Per-outcome state
and handoff contracts remain authoritative for attempts, phase gates and verdicts.

## Resolve the assignment

Read repository instructions, accepted decisions, supplied references and saved
state before asking questions. Accept these forms:

- Single outcome document: preserve the existing per-outcome loop and state path.
- Group directory or index: read the index and every full selected outcome,
  dependencies, source constraints, handoffs and evidence. The index's membership
  defines scope; if absent, enumerate outcome documents in the directory. If an
  index and directory disagree materially, resolve membership before executing.
- Explicit document set: preserve that exact membership; record user ordering.
- Contextual prompt: resolve named outcomes from repository evidence, or accept
  an embedded executable outcome with stable identity, criteria and constraints.
  Save the accepted specification in project-owned storage before implementation.
- Saved per-outcome or group state: resolve its authoritative references and use
  conservative recovery, never a new attempt budget.

With no scope, discover group directories/indexes and standalone outcome documents
under `outcomes/`. Show paths, identities and known blockers; do not list members
again as standalone choices. Ask which to execute **even if only one exists**;
discovery is not authorization to choose. If none exist, report nothing to
implement and stop. An ambiguous contextual match also needs scope resolution.

A freeform idea without observable acceptance is not executable. Inspect existing
decisions first, then resolve material ambiguity. Use `to-outcomes` when planning
is appropriate and authorized; obtain authorization if the request only authorized
execution. Do not generate a specification and silently start it. Routine choices
inside accepted scope need no question.

Validate project-wide stable outcome IDs, duplicate IDs, duplicate membership,
criterion identities, dependency references, cycles (including reachable external
prerequisites), and conflicting requirements/ownership. Duplicate IDs, cycles and
ambiguous membership block scheduling until reconciled; retain existing state.
For a missing dependency or a localized material conflict, name affected outcomes
and block those paths; continue provably unaffected eligible work. Never silently
choose between contradictory acceptance criteria.

Resolve prerequisites outside selected scope explicitly: identify their documents,
required behavior and current evidence. Sufficient current evidence can satisfy
the dependency without executing that outcome. Otherwise record a prerequisite
wait and the resolving action (verify existing behavior or authorize additional
scope). Do not implement or mutate external outcome state without authorization.
If external evidence is stale, it cannot establish readiness.

## Execution defaults and evidence

Implement and verify in the development environment. Use labelled fixtures and
captured mail, webhooks or other effects where the authoritative criteria allow.
Do not deploy, publish, send real emails or cause real external effects without
explicit authorization; carry forward applicable authorization from the session.
If acceptance explicitly requires real delivery, deployment or another external
behavior, local capture cannot substitute for it. Record the affected criterion,
authorization/capability gap and exact resolving action; continue independent work.
Ask only about material behavior, authority or acceptance evidence, continuing
unaffected work while answers are pending.

Check required verification capabilities early: application control, test data,
browser, visual inspection, accessibility and performance where applicable. Use
available equivalent tools only when they establish the same acceptance evidence.
Missing capabilities produce recorded limitations and INCONCLUSIVE for checks
that cannot run; an observed violation is FAIL. Neither is PASS. Follow the
existing recalibration/no-progress rules rather than retrying unavailable checks.

Verification is a separate assessment against original criteria: inspect actual
code and independently gather observations, fixtures, failure paths and regression
evidence instead of accepting implementation checks as proof. A single agent can
perform distinct implementation and verification phases with these boundaries;
a second agent alone does not make verification independent. Verify must not fix
product code. All fixes consume an implementation attempt under the existing gate.

Record the actual inspected workspace: repository/worktree identity, HEAD plus
content digests or immutable snapshots of relevant tracked changes, untracked
inputs, configuration, fixtures, and relevant environment/tool versions. Exclude
irrelevant runtime logs from code identity, but retain the evidence itself. Record
commands/actions, observations and accessible artifacts. A SHA alone does not
identify a dirty tree; worker checks or historical PASS cannot certify integration.

After every implementation, integration or environment/fixture change, assess
impact across selected outcomes and their prerequisites. Before more dependent
work or completion, mark potentially affected PASS as INCONCLUSIVE in per-outcome
state, preserve historical proof, and queue affected regressions. If impact cannot
be bounded, invalidate all potentially affected passes. Record an explicit impact
assessment for retained passes. Re-evaluate earlier FAIL/INCONCLUSIVE too. Verify
regressions on the current integrated workspace, through the existing phase loop;
read-only verification consumes no implementation attempts. An unresolved
regression blocks dependents relying on that behavior. Do not stamp old evidence
with a new workspace identity without establishing applicability.
When invalidating a completed outcome, checkpoint `phase: verify`, `step: ready`
and the affected criterion scope; reopen a completed group as `active`. Save the
pending regressions before scheduling more work. Do not leave a contradictory
`complete` checkpoint containing INCONCLUSIVE criteria.

## Scheduling and stopping

One coordinator owns scheduling, integration and state writes. Recompute readiness
from full documents and current evidence on entry and after every phase or change;
planning-time `ready`/`blocked` labels are hints, not gates or acceptance.

1. Reconcile interrupted active work first using per-outcome recovery rules.
2. Assess pending regressions and prerequisites before selecting dependent work.
3. An outcome is eligible when its definition is executable, its own blockers are
   resolved, required prerequisite behavior has current sufficient PASS evidence,
   and its next action passes the per-outcome state gates. Completion requires all
   criteria, even when a prerequisite only needs a specified subset of behavior.
4. Honor explicit user sequence. Never reorder it silently to bypass dependencies;
   report a conflict and obtain a revised order/scope if necessary. Unordered work
   can continue if outside that conflict. Otherwise choose among eligible outcomes
   by suggested index order, then stable outcome ID for ties/omissions. This is a
   dependency schedule, not blindly following index row order.
5. Run the existing implement → independent verify → recalibrate loop, recording
   attempts before implementation and consuming saved handoffs exactly once.
6. On completion or blocking, checkpoint and automatically choose the next eligible
   outcome. Do not pause for progress reports or ask whether to continue. A blocked
   outcome does not halt unrelated work. Distinguish its direct blocker from a
   dependent's `waiting_on` entry with the prerequisite and required resolving action.
7. Finish only when every selected required criterion has current accessible PASS
   evidence and no pending regression/active invocation remains, or no remaining
   action can proceed. The latter is a blocked group, never partial completion.
   Capability diagnostics must obey the existing no-progress rule.

Report completed outcomes, direct blockers, prerequisite waits, tests actually run
and evidence links, unrun/unavailable checks, branch/worktree identity, next actions
and application run instructions when applicable. A scoped overall PASS cannot
certify an outcome or group. On resume, recheck the same completion predicate.

## Group checkpoint version 1

For groups and explicit sets, store `.agents/work/groups/<group-id>/state.yaml`
by default. Use the normalized group folder name; explicit sets need a stable
project-unique identity derived from their selected canonical references. Detect
identity/path collisions; never overwrite another group's state. Keep an event log
beside the checkpoint for scheduling and impact assessments. Single outcomes still
use `.agents/work/<outcome-id>/state.yaml` without needing a group wrapper.

All fields below are required; paths are repository-relative unless absolute.
This checkpoint references outcome truth instead of copying verdicts or attempts.
Before claiming ownership, inspect other group checkpoints referencing the same
outcomes. Two group coordinators must not dispatch or write the same outcome;
reconcile active ownership or wait until the existing coordinator releases it.

```yaml
schema_version: 1
group_id: example
phase: active # active | complete | blocked
selection:
  references: [outcomes/example/first.md, outcomes/example/second.md]
  index: outcomes/example/README.md # null for an explicit set without an index
  fingerprint: "<digest of membership, full definitions, dependencies and accepted decisions>"
  decisions: [] # authoritative paths or saved accepted decisions
  user_order: [] # explicit ordered IDs, otherwise []
  suggested_order: [example-first, example-second]
outcomes:
  - {id: example-first, reference: outcomes/example/first.md, state: .agents/work/example-first/state.yaml}
  - {id: example-second, reference: outcomes/example/second.md, state: .agents/work/example-second/state.yaml}
external_prerequisites: [] # {id, reference, required, evidence, resolving_action}
workspace:
  repository: "<canonical repository identity>"
  worktree: "<absolute coordinator worktree path>"
  branch: codex/outcomes/example
  base: {reference: origin/main, commit: "<resolved base SHA>", freshness: "<fetch observation or explicit fallback>"}
  integrated: "<actual content/snapshot and relevant environment identity>"
coordinator: "<single owning session; explicit takeover after confirming old writer stopped>"
active: [] # {outcome_id, phase, invocation_reference, worker_worktree}; sequential: at most one
blockers: [] # {outcome_id or group_id, code, reason, resolving_action}
waiting_on: [] # {outcome_id, prerequisite_id, required, resolving_action}
pending_regressions: [] # {outcome_id, criteria, cause, workspace, next}
schedule_log: .agents/work/groups/example/events.md
next: Select first eligible outcome after reconciling referenced state.
```

Initialize only after resolving scope and work identity; do not create runtime
files in reusable skills. The `base.reference` above is illustrative: resolve the
actual default branch, never assume `main`. Record scheduling decisions, rationale,
impact assessments, integration events and resolving evidence in `schedule_log`.
Blocker/wait lists are routing aids; reconcile them from per-outcome state on
every entry. They must not contradict or override per-outcome gates.

Before dispatch, save group intent/active invocation identity, then save the
per-outcome running checkpoint (including attempt increment) before invoking work.
The invocation reference identifies a durable dispatch record in the schedule log,
not a handoff that has yet to be produced.
Save artifacts before state references. After a handoff, checkpoint its consumption
in per-outcome state, then update the group. Use whole-document temporary writes
and atomic replacement where available; stop dispatching if persistence fails.
Since two files are not an atomic transaction, reconcile intent against per-outcome
state after interruption: group intent alone does not prove an attempt started;
per-outcome `running`/`returned`/`ready` determines recovery and consumption. Do not
replay a completed phase because group state lagged. Persist integration intent
before applying worker changes; record resulting workspace and affected evidence
before accepting verification. Recover a partial integration by inspecting actual
history/changes; never blindly reapply it.

At takeover, confirm the previous coordinator and workers have stopped or are
safely controlled before taking write ownership. Unknown schema, invalid fields,
missing log/artifacts, changed selection/fingerprint, conflicting identity or
uncertain active work requires reconciliation; preserve originals and history.
Missing group state is not a new run when branches, logs or per-outcome work exist.
Reconstruct only from trustworthy artifacts, confirming uncertain scope/history
with the human. Never infer a fresh budget. Per-outcome schema remains version 1;
existing single-outcome state needs no migration. Attaching it to a group requires
identity/evidence/branch validation, not reinitialization. No silent migration from
unknown group versions or legacy unversioned state is supported.

## Branch and worktree policy

Before implementation inspect repository default/current branches, working tree,
worktrees, local/remote branch collisions, existing group/per-outcome state and
recorded work branch. Honor explicit user branch instructions and record them.

For a new group, resolve the default branch from repository/remote configuration
(for example remote symbolic HEAD, checked against `git ls-remote --symref <remote>
HEAD`); reconcile conflicting configuration. Select the configured remote rather
than assuming `origin`. Refresh its default-branch ref when available and
authorized. Record fetched ref/SHA and observation. If remote freshness cannot be
established, disclose why; fallback to a known local configured default ref only
when repository/session policy explicitly permits an offline start, recording its
SHA and unknown freshness. Otherwise block branch creation for the necessary
decision. Never describe an offline base as latest remote state.

Create a dedicated deterministic branch `<repo-prefix>outcomes/<group-id>` from
that resolved base; use `codex/outcomes/<group-id>` absent a repository convention.
Validate branch names and detect normalized identity collisions. Inspect existing
local/remote names and worktrees first. A colliding name is not proof of ownership;
reuse only after recorded identity/history validation or explicit reconciliation.
Do not invent suffixes that hide existing work or reset a colliding branch.

For resumed work, reuse the recorded branch/worktree, validate repository identity,
base ancestry, expected integration history, current HEAD/content and saved active
work. Legitimate subsequent commits require evidence impact assessment; unexpected
rewrites, missing branches/worktrees, conflicting checkout/state or ownership need
reconciliation from retained history and a human decision where uncertain. Never
recreate a resumed branch from the default and lose accumulated work.

Preserve unrelated changes: never reset, clean, force-switch, overwrite or
automatically stash them. Prefer an isolated worktree on the dedicated branch
when current work or branch identity makes switching unsafe. Existing dirty work
stays where it is; do not silently copy it into execution. If authorized scope
requires those changes, reconcile their ownership and accepted baseline. If safe
isolation is unavailable, record the exact blocker and required decision. Persist
branch/worktree/base identity before implementation and report it at completion.
Single-outcome runs inspect and preserve their branch identity under existing
state rules; the dedicated group-branch default does not force migration of them.
Creating a branch grants no permission to push, open a PR, merge or deploy.

## Optional parallel implementation

Sequential single-agent execution is the default. Delegate only when the user or
applicable instructions authorize it, runtime agents and isolation are available,
and the outcomes are explicitly assessed suitable for concurrent implementation.
Dependency independence alone is insufficient: assess overlapping files,
migrations, shared configuration, generated assets and integration risk. If safe
coordination cannot be established, record why and run sequentially.

The coordinator alone owns scheduling, integration and canonical state writes.
Use isolated worker worktrees or an equivalent supported mechanism, record their
base, assigned outcome/criteria and invocation identities in `active`, and charge
each invocation to its outcome before dispatch. Workers return changes/handoffs;
they do not write canonical checkpoints or reset budgets. Do not dispatch an
outcome to two implementers or allow workers to integrate into the coordinator.

Integrate each worker's changes into the coordinator's current code before
acceptance verification; inspect and resolve conflicts without discarding work.
Record integrated content identity, recheck dependencies and assess evidence
invalidation after each integration. Worker-branch PASS is only historical
evidence. Independently verify the assembled application and affected regressions
on the coordinator workspace. Freeze relevant inputs during verification or
invalidate results if another integration changes them. Serialize integration
and checkpoint writes even when implementation runs concurrently. On interruption,
reconcile worker status and partial integration before dispatching replacements;
per-outcome attempt and recovery gates always apply.
