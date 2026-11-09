# Onboarding interface review

## Scope and coverage

Scope: the first-owner shop setup form and saved/device prompt. Django templates, native form controls, plain CSS/JavaScript, and the existing WashDay fonts, theme tokens and spacing conventions. Recon included README.md, docs/ui-audit/README.md, templates/auth_base.html and static/css/{app,tokens}.css. No repository AGENTS.md, CONTRIBUTING.md or standalone design-system guide was present.

Applied [better-interface](https://github.com/jakubkrehel/skills/blob/main/skills/better-interface/SKILL.md), [better-layout](https://github.com/jakubkrehel/skills/blob/main/skills/better-layout/SKILL.md), [better-ui](https://github.com/jakubkrehel/skills/blob/main/skills/better-ui/SKILL.md), and their accessibility, writing, typography and colors domain skills. Existing owner settings and device enrollment are outside the visual review; the walkthrough verifies the handoff to Add device.

| Domain | Evidence inspected | Result |
| --- | --- | --- |
| Accessibility | Native labels/buttons, accessible action names, keyboard Add/Remove/Undo, visible focus, focused error summary, input errors and stable status region | Clear in browser checks; screen-reader speech not verified |
| Layout | 320, 390, 620, 768 and 1280px widths; RTL at 320px; longer labels; 200% CSS zoom | Clear in tested states |
| Writing | Section instructions, optional items, remove/undo feedback, minimum-service error, saved/device prompt | Clear |
| Typography | Existing Figtree family, inherited weights, wrapping labels, tabular numeric inputs, 16px mobile input text | Clear |
| Colors | Light/dark text, input borders, focus and primary action token pairs | Clear; secondary text minimum 5.11:1 in light and 6.91:1 in dark |
| UI | Consistent controls, shared radius/theme tokens, reduced-motion-safe pressed state, instant row updates | Clear |

## Resolved findings

| Severity | Domain | Location | Before | After | Why |
| --- | --- | --- | --- | --- | --- |
| MEDIUM | Layout | templates/owner/onboarding.html:10; static/css/owner-onboarding.css:17 | Repeated full-width nested cards and vertically stacked fields | Centered 920px form, horizontal desktop rows, paired mobile billing/price controls and shared section actions | Shared edges and related controls reduce scrolling |
| MEDIUM | Writing/accessibility | static/js/owner-onboarding.js:35 | Delete checkboxes leave every field taking up space | Named Remove buttons collapse a row to a summary with Undo; values and formset indices survive | Reversible actions stay clear and keyboard reachable |
| MEDIUM | Accessibility | templates/owner/onboarding.html:9 | Validation has no overall recovery cue | Focused error summary plus the existing inline form/formset errors | Errors name the next action and remain easy to find |

No actionable interface findings remain within the tested scope.

## Verification

- `uv run pytest --ds=config.test_settings -q`: all 334 tests passed.
- `uv run python manage.py check` and `git diff --check`: passed.
- Chromium: add custom rows; remove and undo with Enter; confirm focus remains on Undo and new-row focus enters its name; preserve prices after Undo and after a duplicate-name validation error; reject removing all services and allow restoring them.
- Chromium: verify visible controls remain inside the viewport at each listed width; light/dark screenshots inspected; no horizontal overflow at 320px RTL, with longer labels or at 200% CSS zoom.
- Record the actual form submission and verify Add device selects Main Branch and Shared counter tablet.
- Not verified: screen-reader speech, physical iOS Safari, native browser zoom separate from the CSS zoom stress test, translated production locales. Google consent is outside this recording.

## Verdict

Approve within the inspected scope and tested browser states; the platform-specific checks listed above remain unverified.
