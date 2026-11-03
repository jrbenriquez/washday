---
name: implement
description: Make scoped software changes to satisfy a specific outcome or documented recalibration plan.
---

# Implement

## Shared handoffs
Read [Handoff contracts](references/HANDOFFS.md) for required result fields,
evidence rules, examples, and phase routing.

## Inputs
- Assigned outcome and acceptance criteria.
- Constraints and any recalibration plan.
- Current repository state.

## Procedure
1. Inspect relevant code, tests, repository instructions, and optional `.agents/capabilities/CAPABILITIES.md`.
   Establish the affected app's stack from its manifests/lockfiles, configuration
   and accepted decisions. Follow existing conventions; generic stack preferences
   apply only to genuinely new or undecided choices under the shared policy.
2. Confirm the current branch and repository state; do not discard unrelated changes.
3. Plan the smallest coherent change that satisfies the assigned criteria.
4. Implement and add or update appropriate tests.
5. Run fast, relevant checks available in the environment.
6. Return an implementation result using the shared contract, including changes,
   checks, assumptions, gaps, blockers, and the next actionable step. This is not
   an acceptance verdict.

## Boundaries
- Do not alter the outcome's acceptance criteria.
- Do not declare the outcome verified; hand off to `verify`.
- Follow project-specific instructions when present; capabilities are optional.
