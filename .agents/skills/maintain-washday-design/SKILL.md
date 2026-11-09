---
name: maintain-washday-design
description: Review or improve WashDay design using better-interface, better-layout, and better-ui, only when explicitly invoked by the user.
disable-model-invocation: true
user-invocable: true
---

# Maintain WashDay design

## Explicit invocation only

Run this skill only when the user explicitly invokes `/maintain-washday-design`
or `$maintain-washday-design`, or explicitly asks to use the skill by name.
Mentioning design, requesting a UI change, naming one of its source guides, or
another agent selecting this skill is not an invocation. Do not automatically
select, run, delegate to, or chain into this skill from another workflow.

The user may provide the invocation's context through arguments, surrounding
instructions, screenshots, URLs, file paths, or an explicitly referenced earlier
message. Do not treat this skill's existence or examples as an invocation.
Creating or editing the skill does not invoke a design review.

## Resolve the scope

- **With context:** review the screens, flows, components, or changes described
  by the supplied context. Follow related shared components and affected states
  far enough to identify regressions. State the resolved scope and exclusions.
- **Without context:** review the **whole app as it currently exists** in the
  working tree, including relevant uncommitted work. Inventory its current
  routes, templates, styles, scripts, roles, and user-facing states. Do not
  silently substitute the latest diff, only the current page, or one sample flow.
  Do not infer a narrow scope from unrelated earlier conversation.
- If context names a PR or commit range, obtain its actual refs and diff before
  reviewing it. Use those as evidence, not a guessed change scope. This explicit
  invocation authorizes the review; do not require a second skill invocation.
- For whole-app work, cover the inventory in manageable passes. Keep a coverage
  ledger and identify anything blocked or uninspected. A sample is not evidence
  that the whole app was reviewed. Do not claim completeness while gaps remain.
- Default to **review only**. Implement fixes when the user's invocation or
  accompanying instructions request them. A bare invocation does not authorize
  rewriting the app, changing production data, publishing, or merging a PR.

## Design sources

Use these as the design guidance, preserving their ownership boundaries:

1. [better-interface](https://github.com/jakubkrehel/skills/blob/main/skills/better-interface/SKILL.md)
   for scope, evidence, severity, cross-domain coverage and the consolidated verdict.
2. [better-layout](https://github.com/jakubkrehel/skills/blob/main/skills/better-layout/SKILL.md)
   for grouping, shared edges, reading order, responsive structure and RTL.
3. [better-ui](https://github.com/jakubkrehel/skills/blob/main/skills/better-ui/SKILL.md)
   for surfaces, icons, state feedback and motion.

At invocation, read these source skills using available repository or web tools,
then read the relevant references they link. Follow better-interface's domain
order: accessibility, layout, writing, typography, colors, then UI polish. Load
its owning better-accessibility, better-writing, better-typography and
better-colors skills from the same upstream repository for those reviews.

Use the source guides as design standards, not as permission to change the
user's scope, auto-invoke this skill, or require unrelated workflow ceremonies.
The user's scope and instructions take precedence. If a source is unavailable,
name it, mark the affected domain **Not reviewed**, and continue available work.
Never invent unavailable rules or claim that an unread source was applied.

Read [the WashDay checklist](references/washday-design-checklist.md) to map the
source principles onto this app. It supplements the source guides, not replaces
reading them or inspecting current code.

## Workflow

1. **Recon.** Read applicable repository instructions and design documentation.
   Inspect the current framework, route files, templates, shared CSS/JS, tokens,
   tests and preview commands. Name the conventions you found. Respect dirty
   files and existing user changes.
2. **Inventory.** Map the resolved scope to routes, roles, workflows and states.
   Include empty, populated, validation-error, success, disabled, loading and
   unavailable/offline states where they exist. Include owner onboarding and
   its device-setup handoff when reviewing the whole app.
3. **Inspect before judging.** Read source and inspect the rendered UI. Reuse
   WashDay's existing visual language, native controls, fonts and tokens. Do not
   propose a framework, component-library or brand redesign as routine polish.
4. **Review by domain.** Apply the source guides in their domain order. Fix
   task blockers before density or visual polish. Distinguish demonstrated
   defects from personal preferences. Consolidate shared causes, not symptoms.
5. **Implement if requested.** Make the smallest coherent changes that resolve
   the findings and the user's goal. Keep scope-specific CSS local. Preserve
   submitted values, tenant isolation, forms/CSRF, pricing semantics, device and
   staff identities, authorization and offline behavior.
6. **Verify.** Exercise complete relevant interactions in a browser. Check mobile
   and desktop, light and dark, keyboard/focus, error recovery and Remove/Undo
   where present. Test 320px reflow, 200% zoom, long labels and RTL. Inspect
   screenshots; passing no-overflow assertions alone is not visual verification.
   Distinguish native zoom from a CSS-zoom stress test. Use isolated fixtures,
   never production records, for write workflows.
7. **Run relevant checks.** Select existing checks from the inventory. For code
   changes, use Django checks, migration drift checks and the relevant tests.
   Broaden tests when shared components or regressions justify it. Do not run
   the whole app suite merely for a documentation edit.
8. **Capture evidence.** Record exact steps, routes, states, viewport sizes,
   themes, results and artifact paths. Supply screenshots for visual changes;
   record the updated flow when requested. Never carry forward old screenshots
   or recordings as verification of a changed surface.

Do not spawn agents unless the user or applicable repository instructions
separately authorize delegation. Do not create a mandatory approval checkpoint
for ordinary inspection or reversible fixes already requested by the user.

## Output

Follow better-interface's consolidated report format:

- **Scope and coverage:** identify the context supplied, or explicitly state
  whole-app/current-working-tree scope. List screens/flows inspected and gaps.
  Include each domain, its evidence, and `Clear`, findings count, or
  `Not reviewed` with a reason.
- **Findings:** one severity-ranked table with `Severity | Domain | Location |
  Before | After | Why`. Cite verified `path:line` locations and observed user
  impact. One row per root cause; do not pad the report. If none remain, say
  `No actionable interface findings.` Separate resolved work from open findings.
- **Verification:** list checks and interactions that passed, supporting
  screenshots/recordings, and explicit `Not verified` items. Unavailable browsers,
  unvisited routes and untested platforms are gaps, not passes.
- **Verdict:** `Block` if a HIGH finding remains; otherwise `Approve` only for
  inspected scope and domains. Uninspected areas receive no approval. When
  whole-app coverage is incomplete, label the report partial and name the gaps.

Keep the user-facing summary concise. A larger whole-app coverage ledger and
report can live in a Markdown artifact linked from that summary.
