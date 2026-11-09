# Onboarding branch-step review

## Scope and coverage

The requested flow is homepage → owner sign-in → shop details → branch details → shared-device setup. The design review covers onboarding and its device handoff, including the branch form's initial, populated, validation-error and saved states. Broader owner/staff workflows are outside this review. Recon included README.md, docs/ui-audit/README.md, the local WashDay checklist, auth_base.html, and shared app/owner-form/theme styles. No AGENTS.md was present.

Applied the explicitly invoked [maintain-washday-design skill](../../../../.agents/skills/maintain-washday-design/SKILL.md). Read upstream [better-interface](https://github.com/jakubkrehel/skills/blob/main/skills/better-interface/SKILL.md), [better-layout](https://github.com/jakubkrehel/skills/blob/main/skills/better-layout/SKILL.md), [better-ui](https://github.com/jakubkrehel/skills/blob/main/skills/better-ui/SKILL.md), the accessibility/writing/typography/colors owning skills, and relevant form, focus, grouping, adaptivity, contrast, typography, surface, icon and animation references.

The implementation keeps Django templates, native controls, Figtree, semantic theme tokens, compact shared edges, and one primary action per step.

| Domain | Evidence inspected | Result |
| --- | --- | --- |
| Accessibility | Native labels/time inputs/checkbox/buttons; keyboard Add/Remove/Undo; branch tab order, focus ring and Enter submit; focused error summary; invalid field and linked inline error | Clear in exercised Chromium states; screen-reader speech not verified |
| Layout | Branch screenshots at 320, 390, 620, 768 and 1280px in both themes; 320px RTL and long labels; 200% CSS zoom; normal-flow footer | Clear in tested states |
| Writing | Step numbers, required branch fields, hours/24-hour hints, duplicate-code recovery and saved branch name in device prompt | Clear |
| Typography | Existing fonts/weights, wrapping labels/help, 16px mobile input text, readable heading hierarchy | Clear |
| Colors | Computed foreground/background samples in contrast.json; light/dark rendered screenshots; shared input and focus tokens | Clear: sampled normal text minimum 5.25:1 light and 6.45:1 dark; input boundary 5.68:1 light and 7.94:1 dark |
| UI | Existing neutral surfaces and radii, native time controls, currentColor success icon, RTL continuation arrow, reduced-motion press behavior | Clear |

## Resolved findings

| Severity | Domain | Location | Before | After | Why |
| --- | --- | --- | --- | --- | --- |
| MEDIUM | Layout | owner/onboarding.py:159; templates/owner/onboarding_branch.html:5 | Catalog submission automatically created Main Branch and immediately offered device setup | Explicit branch step with name, editable ONE code, hours and checked Simple workflow | Owners can configure their branch before assigning a device |
| MEDIUM | Writing | templates/owner/onboarding_device.html:5 | Device prompt always named Main Branch | Prompt and device handoff use the saved branch | The invitation must identify the branch the owner configured |
| LOW | UI | static/css/owner-onboarding.css:53 | Continuation glyph pointed right in RTL | Mirror the arrow in RTL | Directional icon follows progression |

No actionable interface findings remain within the inspected scope.

## Verification

- `uv run pytest --ds=config.test_settings -q`: 372 passed on SQLite. A final focused run after the lock-order adjustment passed all 37 onboarding/reset tests.
- Django system checks, migration drift check and `git diff --check`: passed.
- `uv run python scripts/check_onboarding_browser.py`: passed against a temporary database. Records the actual app from homepage and sign-in through catalog save, branch save, invitation creation, installation instructions, setup-code entry, device enrollment and return to Access and devices showing Enrolled.
- Google consent is outside verification. The recording intercepts the local Google-login POST and installs an isolated Django test-owner session. No application authentication bypass was added. Local browser enrollment is enabled only for this temporary development run; physical Home Screen installation is not represented.
- Browser checks: default ONE code and checked Simple mode; case-insensitive duplicate error with retained name/code/hours; focused recovery summary and linked error; device-step gating; custom code and Full workflow persistence; service/piece keyboard Add/Remove/Undo; responsive/theme/RTL/zoom/long-label/reduced-motion probes.
- Unit checks additionally cover required/invalid fields, forged connection mode, CSRF/authentication, same code in a different shop, repeated submissions, progress/resume and safe reuse of a reset test shop's branch/counters.
- [30-second walkthrough](flow.mp4), [initial desktop branch form](branch-desktop.png), [320px light](branch-320-light.png), [390px dark](branch-390-dark.png), [duplicate-code error](branch-duplicate-error.png), [RTL](branch-rtl-dark.png), [200% CSS zoom](branch-zoom-light.png).
- Not verified: external Google OAuth/consent, screen-reader speech, physical iOS Safari/Home Screen install, native browser zoom separate from the CSS stress test, production translations. Other app screens receive no design verdict here.

## Verdict

Approve for the inspected onboarding and handoff scope and tested Chromium states, with the platform boundaries above.
