---
name: recalibrate
description: Diagnose failed or inconclusive verification and produce a bounded high-level adjustment plan before retrying implementation.
---

# Recalibrate

## Shared handoffs
Read [Handoff contracts](references/HANDOFFS.md) for required result fields,
evidence rules, examples, and phase routing.

## Inputs
- Original outcome and constraints.
- Previous implementation result.
- Verification result with evidence and failed/inconclusive criteria.
- Prior attempts and adjustment plans.

## Procedure
1. Identify exactly which criteria failed or remain unverified.
2. Separate observed facts from hypotheses about root cause.
3. Determine whether the issue is implementation, assumption, environment, dependency, or verification coverage.
4. If evidence is insufficient, request targeted diagnostics instead of speculative changes.
5. Propose the smallest high-level adjustment that addresses the likely cause.
6. State what already-working behavior must be preserved and what to reverify.
7. Flag repeated non-progress, conflicting requirements, or risks that warrant human escalation.

## Output
Return a recalibration result using the shared contract. Distinguish a SUPPORTED
cause from a HYPOTHESIS, cite evidence, and identify the scoped adjustment or
targeted diagnostic action. Include preservation constraints and reverification
scope. Use the shared decisions: `REIMPLEMENT`, `GATHER_EVIDENCE`, or `ESCALATE`.

Never silently change acceptance criteria or implement code during recalibration.
