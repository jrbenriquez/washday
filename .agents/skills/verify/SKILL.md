---
name: verify
description: Independently assess implementation against explicit acceptance criteria and return evidence-backed results.
---

# Verify

## Shared handoffs
Read [Handoff contracts](references/HANDOFFS.md) for required result fields,
evidence rules, examples, and phase routing.

## Inputs
- Original outcome document and acceptance criteria.
- Implementation result (or recalibration diagnostic request and findings).
- Current implementation and repository state.
- Optional project capability registry at `.agents/capabilities/CAPABILITIES.md`.

## Procedure
1. Identify observable evidence required for each criterion.
2. Discover applicable project-specific verification skills, scripts, and application controls without assuming they exist.
3. Run appropriate automated tests, checks, and behavioral inspection where feasible.
4. Record the commands/actions performed, environment, results, and evidence locations.
   Identify inspected code, configuration and fixtures, including dirty/untracked
   inputs. For groups, inspect the coordinator's integrated workspace and affected
   earlier criteria; worker-branch checks cannot establish integrated acceptance.
5. Return a per-criterion status: `PASS`, `FAIL`, or `INCONCLUSIVE`.
6. Note regression risks and untested paths. A test that was not run cannot count as a pass.

## Output
Return a verification result using the shared contract. Cover every criterion
in the assigned scope exactly once, apply the shared overall-status rule, and
identify corrective targets or missing evidence for recalibration.

## Independence
Do not accept the implementer's success claim as evidence. Do not weaken or edit acceptance criteria. Do not modify product code as part of verification; report defects for recalibration.
