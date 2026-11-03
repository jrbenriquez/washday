<!-- Generated from docs/WORK-STATE.md by scripts/sync-handoffs.py. Do not edit this copy. -->

# Outcome state, retries, and resume

The orchestrator owns one project-local YAML state file per outcome, suggested
`.agents/work/<outcome-id>/state.yaml`. Put handoffs and evidence beside it or
reference existing project artifacts. Never write runtime state into installed
skill directories or `.agents/capabilities/`. All four skills keep their existing
responsibilities and handoff formats. This document specifies orchestration
policy around those handoffs, not a runtime or storage service.

## Schema version 1

All fields below are required. Paths are relative to the outcome directory unless
absolute. References must be accessible; evidence IDs are qualified by their
handoff path so IDs reused in later handoffs cannot collide.

```yaml
schema_version: 1
outcome_id: csv-export
outcome:
  reference: ../../../outcomes/csv-export.md
  fingerprint: "<digest of authoritative outcome including criteria and constraints>"
phase: implement # implement | verify | recalibrate | complete | blocked
step: ready # ready | running | returned; terminal phases use ready
scope: [AC-01, AC-02]
implementation_attempts:
  started: 0
  maximum: 3
workspace: "<identity of relevant code, configuration, and verification environment>"
criteria:
  - id: AC-01
    status: PENDING # PENDING | PASS | FAIL | INCONCLUSIVE
    evidence: [] # [{handoff: handoffs/verify-1.yaml, id: V1}]
    verified_workspace: null
    reason: Not yet assessed.
  - id: AC-02
    status: PENDING
    evidence: []
    verified_workspace: null
    reason: Not yet assessed.
latest_handoff: null # or {type: implementation, reference: handoffs/implement-1.yaml}
latest_verification: null # or handoffs/verify-1.yaml
recalibrations: [] # ordered {reference: handoffs/recalibrate-1.yaml, decision: REIMPLEMENT}
blockers: [] # {code: attempt_limit, reason: ..., next: ...}
next: Implement filtered export and retain the empty-result header.
```

`phase` is also the completion status: only `complete` means verified completion;
`blocked` means stopped without completion. Other phases are active work. No
separate completion boolean can contradict it. `step` describes the current
phase invocation, not acceptance status. `scope` contains known criterion IDs
assigned to that invocation; terminal phases use `[]`.

`maximum` is a positive integer, default **3**, configurable before work starts.
`started` is a nonnegative integer, never reset during resume. The budget is
outcome-wide, including initial implementation and partial-scope invocations.
Record an explicitly authorized budget change before using it. Never raise the
limit automatically, including after blocking or changing scope.

`workspace` must identify the actual inspected inputs, including uncommitted
changes and relevant environment/configuration. A commit ID alone is insufficient
for a dirty tree. A content digest or immutable snapshot plus environment record
is suitable; no specific tool is required. `verified_workspace` records the
context of a verdict. Null means none has been established.

`latest_handoff` points to the latest accepted, unchanged structured result.
`latest_verification` retains the latest verification result even after
recalibration or implementation. Criterion evidence can refer to earlier retained
verification handoffs. Recalibration records retain each accepted decision and
its full handoff reference. Keep referenced artifacts; do not overwrite a handoff
that supports a saved verdict. Blockers state the impediment and what would
permit progress. `next` names the pending action or requested human decision.

## Checkpoints and attempt accounting

1. Before invoking a phase, save its phase, scope, `next`, workspace identity,
   and `step: running`. Before a **new implement invocation**, check
   `started < maximum` and increment `started` in that same checkpoint.
   If saving fails, stop before invoking the skill. Never refund a started attempt.
2. Validate the returned handoff against the shared contracts. Save the full
   handoff first, then checkpoint its reference with `step: returned`. It must
   match the outcome, invocation scope, and inspected workspace. Refresh the
   workspace identity after implementation or diagnostics and invalidate affected
   prior verdicts before applying results. Do not consume
   malformed or stale results as success; request correction without rerunning
   implementation. If correction is unavailable, block.
3. Apply a returned result: update criterion verdicts and evidence for verification,
   append a recalibration decision once per handoff reference, choose the next
   phase from the table, and checkpoint `step: ready`. Preserve the latest
   verification reference when a later non-verification result arrives.
4. Write each state checkpoint as a whole document using a temporary file and
   replacement where available. Retain the last valid checkpoint on write failure.
   A referenced handoff must exist before publishing a checkpoint that names it.
   Only one coordinator may write an outcome at a time. Delegated workers return
   artifacts without writing canonical state; group coordination and isolated
   parallel implementation follow [Group orchestration](GROUP-ORCHESTRATION.md).

A correction to a report is not another implementation attempt. Verification,
recalibration, and read-only diagnostics do not consume implementation attempts.
A change to product code is implementation, including a diagnostic code change,
and must pass the implementation budget gate. Recalibrate and verify never
silently take over implementation work.

## Transition reference

Every transition requires a valid checkpoint and a current handoff when applicable.
The attempt gate applies to **every new implement invocation**, including staying
in implement after INCOMPLETE. An unchanged interrupted invocation is handled by
resume rules instead of being counted again.

| From | Observation or decision | To / action |
| --- | --- | --- |
| New outcome | Valid outcome; no previous work | implement, ready, started 0 |
| implement | READY_FOR_VERIFICATION | verify the assigned scope |
| implement | INCOMPLETE | implement remaining scope if budget allows; otherwise blocked |
| implement | BLOCKED | blocked with the reported impediment |
| verify | FAIL or INCONCLUSIVE | recalibrate failed/inconclusive criteria with full result |
| verify | PASS, some criteria unassessed | implement remaining scope, subject to attempt gate |
| verify | PASS, prior evidence stale | verify affected criteria before completion |
| verify | All required criteria have current PASS | complete |
| recalibrate | REIMPLEMENT | implement with adjustment and preservation constraints, subject to attempt gate |
| recalibrate | GATHER_EVIDENCE | gather scoped diagnostics, then verify affected criteria |
| recalibrate | ESCALATE | blocked with decision/action requested |
| Any active phase | Missing essential evidence, unsafe recovery, save failure, conflicting requirements, or no progress | blocked |
| Any proposed new implementation | started >= maximum | blocked with code attempt_limit |
| complete | Same outcome and all evidence still current | remain complete; return saved report |
| complete | Relevant inputs changed; prior PASS no longer established | verify affected criteria |
| blocked | Impediment unresolved | remain blocked; report saved blocker |
| blocked | Impediment explicitly resolved and state reconciled | resume the action in next, with scope and all gates checked |

Completion and stopping take precedence over selecting more work. The final
allowed implementation may finish its invocation and go through verification
and recalibration. If it verifies all criteria, complete even at the limit. If
another implementation is needed, block immediately rather than starting it.
Diagnostics that could establish acceptance without code changes remain allowed.

Do not spin indefinitely outside implementation: execute a given diagnostic
request once against unchanged inputs. If unavailable, verify as INCONCLUSIVE
and recalibrate; if the next decision merely repeats that request without new
information or an actionable changed condition, block with code no_progress.
Likewise block repeated verification/recalibration cycles that add neither new
evidence nor a distinct, justified action. Do not retry a failed phase automatically
without new information or a specific recovery action.

## Resume and conservative recovery

On every entry, compare state with the authoritative outcome, current workspace,
and referenced artifacts before invoking any skill.

- **Missing state:** initialize only when there is no evidence of previous work
  on the outcome. If handoffs, partial changes, or a previous run are known,
  reconstruct from accessible artifacts with human confirmation of uncertain
  counts or scope; otherwise block. Absence of state must not grant a fresh budget.
- **Invalid state:** preserve the original. Unknown schema versions, parse errors,
  missing fields, duplicate/unknown criterion IDs, invalid enums/counts, or
  contradictory phase/step/verdicts block automatic resume. Do not silently migrate
  the old unversioned work-state template. Report what needs reconciliation.
- **Changed outcome:** an ID, fingerprint, criterion, or constraint mismatch blocks
  until the human confirms the revised scope and reconciled state. Preserve old
  evidence and attempts; never carry PASS forward without assessing applicability.
- **Stale workspace/evidence:** inspect the changes. Mark any potentially affected
  PASS as INCONCLUSIVE with a reason before selecting work; retain old evidence as
  historical. If impact cannot be bounded, invalidate all prior passes. Also
  reconsider earlier FAIL/INCONCLUSIVE verdicts before using them for a new plan.
  Missing or inaccessible proof cannot remain a PASS. Unknown workspace identity
  requires fresh verification or blocking if verification is unavailable.
- **ready:** perform the saved pending action after validation, without replaying
  the preceding completed phase. Consume any newly selected implementation attempt
  only at invocation start.
- **returned:** validate and apply the saved handoff once; do not rerun its producer.
  If its workspace has changed, do not apply stale verdicts or adjustments. Route
  current code to verification, then recalibrate if needed; block if scope is unclear.
- **running:** inspect the saved scope, partial changes, and any completed artifact.
  If a matching handoff was saved before interruption, validate and checkpoint it
  as returned. Otherwise continue the same identifiable invocation, preserving its
  attempt count, only when the remaining work is clear and safe. Do not reapply
  completed changes or repeat non-idempotent actions blindly. If its identity or
  progress cannot be established, block for reconciliation instead of treating a
  fresh invocation as the old attempt. A replacement implementation consumes a
  new attempt and must satisfy the limit.
- **blocked:** a new chat or resume command does not clear a blocker or reset counts.
  Record the resolving evidence or human decision, clear only resolved blockers,
  and save the chosen phase/scope/action before continuing. An exhausted budget
  requires explicit authorization to raise the recorded maximum if more
  implementation is needed. Corrected evidence may permit verification without it.

Before every verification, include previously passed criteria potentially affected
by intervening changes, beyond the implementer's assigned scope. Unaffected passes
may be retained only with an explicit impact assessment in their state reason.
Complete only when every authoritative criterion has current sufficient evidence;
a scoped overall PASS cannot certify the whole outcome.

## Worked checkpoint example

The schema above is an initial example. A plausible later checkpoint is:

```yaml
schema_version: 1
outcome_id: csv-export
outcome:
  reference: ../../../outcomes/csv-export.md
  fingerprint: "sha256:<outcome digest>"
phase: implement
step: ready
scope: [AC-01]
implementation_attempts: {started: 1, maximum: 3}
workspace: "snapshot:export-1; environment:python-3.12-fixture-v1"
criteria:
  - id: AC-01
    status: FAIL
    evidence: [{handoff: handoffs/verify-1.yaml, id: V1}]
    verified_workspace: "snapshot:export-1; environment:python-3.12-fixture-v1"
    reason: Text-filter export omitted the two displayed matches.
  - id: AC-02
    status: PASS
    evidence: [{handoff: handoffs/verify-1.yaml, id: V2}]
    verified_workspace: "snapshot:export-1; environment:python-3.12-fixture-v1"
    reason: Empty-result header was verified; reassess impact after the next change.
latest_handoff: {type: recalibration, reference: handoffs/recalibrate-2.yaml}
latest_verification: handoffs/verify-1.yaml
recalibrations:
  - {reference: handoffs/recalibrate-1.yaml, decision: GATHER_EVIDENCE}
  - {reference: handoffs/recalibrate-2.yaml, decision: REIMPLEMENT}
blockers: []
next: Align export text comparison with table semantics; reverify AC-01 and AC-02.
```

This illustrative checkpoint assumes diagnostics supported the second adjustment;
the referenced files must actually exist in a real run. Resume starts attempt 2,
not attempt 1 again, and does not repeat the saved verification or diagnosis.

## Transition validation (design walkthroughs)

These are table-driven reasoning checks, not an executed end-to-end sample.

| Scenario | Trace and expected stopping point |
| --- | --- |
| Success | started 0 → implement running/1 → returned READY → verify → all current PASS → complete; resume returns saved result |
| Failure | implement/1 → verify FAIL → recalibrate REIMPLEMENT → implement/2 → verify PASS → complete; no direct FAIL-to-implement shortcut |
| Inconclusive | verify INCONCLUSIVE → recalibrate GATHER_EVIDENCE → diagnostics → verify PASS → complete, with no new implementation count; unchanged repeated diagnostic request → blocked/no_progress |
| Interrupted before invocation | implement running/1 saved, no edits yet → safely continue identifiable attempt 1; no increment to 2 |
| Interrupted after return | handoff saved, then crash → recover matching artifact → returned → consume once; no repeated implementation or recalibration append |
| Retry exhaustion | implement/3 → INCOMPLETE, or verify FAIL → REIMPLEMENT → blocked/attempt_limit; started remains 3; automatic resume stays blocked |
| Success at limit | implement/3 → verify all PASS → complete; limit does not discard successful work |
| Evidence invalidation | AC-02 PASS → later relevant edits → AC-02 INCONCLUSIVE → verify AC-01 and AC-02; complete only if both PASS |
| Invalid or missing history | corrupted state or missing state with existing work → blocked for reconciliation; no fresh budget or inferred PASS |
