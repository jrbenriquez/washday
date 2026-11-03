<!-- Generated from docs/HANDOFFS.md by scripts/sync-handoffs.py. Do not edit this copy. -->

# Handoff contracts

These contracts describe results passed between the four core skills. They do
not prescribe files, storage, agent runtimes, tools, or retry policy. Use the YAML
shapes below, or Markdown with the same named fields and values. Empty lists
must be explicit; do not silently omit required information.

## Repository technology choices

Before planning changes, inspect repository instructions, accepted architecture
decisions, relevant code, manifests/lockfiles, tests, CI and runtime configuration.
In an existing app, preserve its languages, frameworks, database, package manager,
dependency versions and established patterns unless the accepted assignment
explicitly requires a change. In a monorepo, follow the affected application's
conventions. A new feature, folder or missing manifest alone does not make the
assignment a new app. Reuse existing capabilities before proposing alternatives.

Generic skill or personal stack preferences are fallback suggestions only for a
genuinely new app or an undecided component, after checking project constraints
and compatibility. They cannot override explicit user decisions or established
project choices. Do not introduce a competing framework, migrate storage, replace
tooling or upgrade dependencies merely to match a preference. If satisfying the
outcome requires a material stack change outside accepted scope, explain the
constraint, compatible alternatives and impact, and resolve that decision before
making the change; continue unaffected work where possible. Record the resulting
decision in project-owned requirements or handoffs so later phases preserve it.
Verify against accepted project constraints, not the verifier's preferred stack;
recalibration must not use a stack rewrite as an unapproved workaround.

## Common fields and evidence

Every result includes `type`, `outcome_id` (from the authoritative outcome),
`criteria` (original criterion IDs in scope), `status`, `evidence`, `blockers`,
and `next`. Phase-specific fields below are also required. Preserve criterion
wording and identifiers; if identifiers are missing, agree stable labels before
handoff without changing their meaning.

`evidence` is a list of records with `id`, `action`, `context`, `observation`,
and `reference`. Context identifies the inspected code/change and relevant
environment; reference points to an accessible artifact or includes the relevant
observation inline. Cite evidence IDs elsewhere in the result. Record actual
observations, including failed or unavailable checks. Implementation evidence
helps verification select checks; it never substitutes for independent assessment.
A bare success claim or inaccessible reference cannot establish a PASS.
Identify relevant code, configuration, fixtures and environment by content digest
or immutable snapshot plus environment record. A commit SHA alone is insufficient
for a dirty tree. Group verification inspects the coordinator's actual integrated
workspace; worker-branch evidence cannot certify the assembled application.

`blockers` lists concrete impediments, or `[]`. `next` describes an actionable
recommendation for the receiving phase, not authority to skip verification or
change requirements. Optional project capabilities may supply actions and
evidence; their absence does not change these contracts or imply failure.
Additional project fields may be included without redefining required fields.

## Implementation result

```yaml
type: implementation
outcome_id: <outcome ID>
criteria: [<assigned criterion IDs>]
status: READY_FOR_VERIFICATION # or INCOMPLETE, BLOCKED
changes: # changed files/components and rationale; [] if none
  - target: <file or component>
    summary: <what changed and why>
evidence: [] # checks run, using common evidence records
assumptions: []
gaps: [] # unfinished work, unrun checks, and known limitations
blockers: []
next: <what verify should inspect, or what is needed to proceed>
```

READY_FOR_VERIFICATION means the assigned implementation is ready to assess,
not that criteria passed. INCOMPLETE means known implementation work remains;
BLOCKED means an impediment prevents proceeding. Checks unavailable in the
implementation environment may be recorded as gaps without preventing handoff
if verification can assess the result elsewhere.

## Verification result

```yaml
type: verification
outcome_id: <outcome ID>
criteria: [<assessed criterion IDs>]
status: PASS # or FAIL, INCONCLUSIVE; derived below
results:
  - criterion: <criterion ID>
    status: PASS # or FAIL, INCONCLUSIVE
    evidence: [<evidence IDs>]
    reason: <what the evidence establishes or why it is insufficient>
    next: <none, corrective target, or specific missing check/evidence>
evidence: [] # independently gathered common evidence records
regression_risks: [] # include untested paths and affected prior passes
blockers: []
next: <completion/remaining scope, or input for recalibration>
```

Return exactly one result for each criterion in scope. PASS requires sufficient
observed evidence that the criterion is satisfied. FAIL requires observed
evidence of a criterion violation. INCONCLUSIVE means evidence cannot establish
either, including unavailable environments, unrun checks, or ambiguous results.
A broken test harness alone is not evidence of a product defect. Mixed evidence
that establishes a violation is FAIL; explain any remaining uncertainty.

Overall status is FAIL if any result is FAIL; otherwise INCONCLUSIVE if any is
INCONCLUSIVE; otherwise PASS. Empty or missing criterion coverage cannot yield
PASS. Overall PASS covers only the listed scope, not the entire outcome.

## Recalibration result

```yaml
type: recalibration
outcome_id: <outcome ID>
criteria: [<failed or inconclusive criterion IDs>]
status: GATHER_EVIDENCE # or REIMPLEMENT, ESCALATE
summary: <failure or evidence gap>
assessment:
  category: <implementation, assumption, environment, dependency, or verification coverage>
  confidence: HYPOTHESIS # or SUPPORTED
  cause: <proposed explanation, or unknown>
  evidence: [<evidence IDs supporting the assessment>]
  uncertainty: <what remains unknown; use none only when justified>
evidence: [] # common records; include cited prior observations with their context
adjustment: <smallest high-level change, or none>
diagnostics: [] # targeted actions and what each would establish
preserve: [] # already-working behavior and constraints
reverify: [<criterion IDs and checks needed after the action>]
blockers: []
next: <concrete adjustment, diagnostic action, or human decision needed>
```

SUPPORTED means cited observations establish the causal explanation, not merely
that a symptom exists. HYPOTHESIS means the explanation remains unconfirmed;
use `cause: unknown` when no explanation is justified. Do not label a plausible
cause as supported merely because a criterion failed.

REIMPLEMENT requires a scoped adjustment justified by evidence. If choosing a
bounded change while the cause remains a hypothesis, explain why the evidence
justifies it and how reverification will test it. GATHER_EVIDENCE requires targeted
diagnostics that discriminate hypotheses or close a specific coverage gap;
`adjustment` is `none`. ESCALATE identifies the impediment and the specific human
decision or external action needed. Recalibration supplies a plan, never code.

## Consumption by orchestrate-work

1. Check outcome identity, criterion scope, required fields, status values, and
   evidence references before routing. Request a corrected handoff from its
   producer if malformed or contradictory; do not infer success from omissions.
   If correction requires unavailable evidence or a human decision, report blocked.
2. Implementation READY_FOR_VERIFICATION → verify the assigned scope.
   INCOMPLETE → return the stated unfinished scope to implement; BLOCKED →
   report blocked and surface the impediment. Neither status is a verification verdict.
3. Verification FAIL or INCONCLUSIVE → recalibrate with the full result, including
   mixed per-criterion statuses, evidence, risks, and blockers, before another
   implementation attempt. PASS → select remaining criteria for implementation,
   or complete only when every required criterion has a supported PASS on the
   current combined implementation. Reverify prior passes affected by later changes.
4. Recalibration REIMPLEMENT → implement with the adjustment, preservation
   constraints, and reverification scope. GATHER_EVIDENCE → arrange the requested
   diagnostics using available capabilities, then verify the affected criteria again
   with the findings. If diagnostics cannot be gathered, return that limitation
   through verification as INCONCLUSIVE and recalibrate or escalate as warranted.
   Diagnostic observations alone do not certify acceptance.
   ESCALATE → report blocked and the requested decision/action to the human.

The orchestrator owns routing and completion; producers own truthful phase
results. These rules add no storage mechanism or attempt/retry policy.

## Examples

The following handoffs concern outcome `csv-export`, whose AC-01 requires
exporting all filtered rows and AC-02 requires retaining the header for no matches.
Paths and commands are illustrative project evidence, not required capabilities.

### Implementation

```yaml
type: implementation
outcome_id: csv-export
criteria: [AC-01, AC-02]
status: READY_FOR_VERIFICATION
changes:
  - target: src/export.py
    summary: Apply the active filter and emit column headers before writing rows.
evidence:
  - id: I1
    action: python -m unittest tests.test_export
    context: Local Python 3.12; working tree with export.py changes
    observation: 6 tests passed; filter coverage uses only numeric columns.
    reference: Inline observation above
assumptions: [Filters use the same comparison semantics as the displayed table.]
gaps: [Text filter behavior has not been checked.]
blockers: []
next: Independently inspect numeric and text filters and the empty-result header.
```

### Verification

```yaml
type: verification
outcome_id: csv-export
criteria: [AC-01, AC-02]
status: FAIL
results:
  - criterion: AC-01
    status: FAIL
    evidence: [V1]
    reason: The displayed text filter matches two rows but export contains zero.
    next: Diagnose comparison semantics for text filters.
  - criterion: AC-02
    status: PASS
    evidence: [V2]
    reason: Export with no matches retains exactly the expected header.
    next: none
evidence:
  - id: V1
    action: Export fixture rows Alice and ALICE with text filter alice
    context: Python 3.12; same working tree handed off by implement
    observation: Table shows two matches; parsed CSV has no data rows.
    reference: Inline fixture and observed counts above
  - id: V2
    action: Export fixture with a filter matching no rows and parse the CSV
    context: Python 3.12; same working tree; columns name and amount
    observation: Parsed CSV contains only the row [name, amount].
    reference: Inline parsed result above
regression_risks: [Large exports were not inspected.]
blockers: []
next: Recalibrate AC-01 while preserving AC-02.
```

If V1 could not run because the fixture environment was unavailable, AC-01
would be INCONCLUSIVE, citing the attempted action and missing evidence; with
AC-02 still PASS, the overall status would be INCONCLUSIVE.

### Recalibration

```yaml
type: recalibration
outcome_id: csv-export
criteria: [AC-01]
status: GATHER_EVIDENCE
summary: Text-filter export produced zero rows where the table showed two.
assessment:
  category: assumption
  confidence: HYPOTHESIS
  cause: Export may compare text case-sensitively while the table ignores case.
  evidence: [R1]
  uncertainty: Comparison code and other filter transformations have not been inspected.
evidence:
  - id: R1
    action: Review verification observation V1
    context: Python 3.12; implementation working tree; Alice and ALICE filtered by alice
    observation: Table matched two rows; export matched zero; cause not yet established.
    reference: Verification result V1, reproduced inline above
adjustment: none
diagnostics:
  - Compare table and export filter evaluation using the same fixture; trace both comparators to establish whether case normalization differs.
preserve: [Empty-result export must retain the name and amount header (AC-02).]
reverify: [AC-01 with mixed-case text and numeric filters, AC-02 empty-result header]
blockers: []
next: Gather comparator evidence, then verify AC-01 again with the findings.
```

If tracing establishes the differing comparators, a subsequent recalibration
can cite that evidence as SUPPORTED and choose REIMPLEMENT with an adjustment
to align export filtering with the table's established semantics.
