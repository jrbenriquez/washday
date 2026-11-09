# Compact owner forms — design maintenance

[Before/after gallery](gallery.html) · [Before layout results](before/checks.json) · [After layout results](after/checks.json) · [Form interactions and contrast](after/form-checks.json)

## Scope and coverage

Requested: inspect existing sections/pages from latest main, improve forms that consume excess space, create a PR and supply before/after screenshots. Base: `a47d960` (main fetched 9 November 2026). This is a **partial whole-app review**, with implementation and detailed review limited to Add staff, Add device, the branch editor and shop branding. Wider page coverage is layout reconnaissance, not approval of every workflow/state.

The app uses Django templates, native forms, plain CSS/JS, Figtree/Saira Condensed/JetBrains Mono and semantic tokens. Conventions were read in `docs/ui-audit/README.md`, the explicitly invoked `.agents/skills/maintain-washday-design/SKILL.md` and its checklist. No AGENTS.md was found. The upstream better-interface, better-layout, better-ui, better-accessibility, better-writing, better-typography and better-colors guides and relevant form/layout/contrast references were read.

| Domain | Evidence inspected | Result for changed forms |
| --- | --- | --- |
| Accessibility | Native labels, help/error associations, Tab order (including native time subfields), focus rings, validation and recovery, 320px reflow, computed contrast | Resolved control boundaries and error focus; screen reader not verified |
| Layout | Four forms at 320/390/768/1280px, both themes; paired fields; 640px reflow, RTL, long labels and CSS zoom 200% | Resolved excess stacking and stretched actions |
| Writing | Branch/device/staff terminology, optional PIN instructions, server errors and success screens | Clear; PIN generation explanation retained as help text |
| Typography | Existing font files and roles, input computed sizing, wrapping labels and help text | 16px inputs in compact forms; no font changes |
| Colors | Computed text, muted text, input boundary, focus and primary button pairs on actual card surfaces, light and dark | Passing sampled pairs recorded in form-checks.json; dedicated control-border token added |
| UI polish | Existing control shapes, card surfaces, native disabled state and action hierarchy | Clear within changed forms; no new motion |

### Route/state ledger

The isolated runner checks 19 routes × 4 widths × 2 themes, plus two signed-out login cases: **154 layout cases** for each phase. All receive no-page-overflow checks and successful response checks. Screenshots for changed pages are retained at desktop/light and phone/dark.

| Screens/flows | Coverage |
| --- | --- |
| Owner dashboard, live branches, branch management, machine administration, catalog editor, count history | Populated fixture layouts checked at all widths/themes; detailed interactions not re-reviewed |
| Branch editor | Populated form, disabled connection mode, validation failure, retained code, correction and successful save; paired hours, checkbox and Cancel remain native |
| Staff | Existing staff card plus empty Add staff form; invalid PIN, retained name, focused error, generated PIN success |
| Access and devices | Empty device list; Add device form, missing personal assignment, retained values, focused error, assigned-phone invitation success |
| Settings | Populated catalog/workflow settings layouts; branding name persisted through multipart form |
| New job, paper intake, job board/list/history/timeline/stub, machines, supplies | Populated fixture layouts checked at all widths/themes; stage dialog opens, Escape closes and focus returns |
| Owner login | Desktop/light and phone/dark layouts checked |
| Owner onboarding and device handoff, device installation/enrollment, staff shift/PIN, invitations/revoke/reassignment, supply receipt/count/request, machine progression, print/export, operator admin, offline/sync | Not visually re-reviewed in this pass; scoped CSS/JS does not target these flows. Existing focused Django tests cover relevant access and onboarding regressions |
| Empty/error/loading/offline states beyond the explicit form cases above | Not reviewed |

## Resolved findings

| Severity | Domain | Location | Before | After | Why |
| --- | --- | --- | --- | --- | --- |
| HIGH | Accessibility | `static/css/app.css:395`, `static/css/owner-forms.css:11` | Compact form boundaries used low-contrast separator color | Dedicated theme-aware control-border token, measured against card surfaces | Native input boundaries need 3:1 non-text contrast (WCAG 1.4.11) |
| MEDIUM | Layout | `templates/owner/staff.html:1`, `templates/owner/home.html:1`, `templates/owner/branch_editor.html:7`, `templates/owner/settings.html:17` | Related fields and stretched actions stack down the page, delaying lists and save actions | Container-responsive fields, bounded device/branch forms, content-sized wrapping actions; labels/help remain visible | Group related fields and reserve full-width stacking for containers where pairs cannot fit |
| MEDIUM | Accessibility | `static/js/owner-forms.js:2`, `templates/owner/compact_field.html:1` | Server errors require finding the failing field again | Focus first aria-invalid compact field; retain labels, help IDs and inline errors | Make keyboard error recovery direct |
| MEDIUM | Functionality | `owner/views.py:207`, `tests/test_authentication.py` | Failed device invitation could fall back to the first branch | Re-render the submitted branch, with regression test using a second branch | Error correction must preserve the intended device branch |
| MEDIUM | Typography | `static/css/owner-forms.css:11` | Owner inputs inherit 15px text | Compact form inputs use 1rem (16px at default settings) | Avoid iOS input focus zoom without reducing control targets |

No unresolved actionable findings within the inspected compact-form scope. Other app areas receive no full interface verdict.


## Measured desktop density

At 1280px/light, card heights include the heading, fields and actions.

| Card | Before | After | Reduction |
| --- | --- | --- | --- |
| staff | 407px | 254px | 38% |
| access | 562px | 385px | 31% |
| branch-editor | 918px | 647px | 30% |
| settings | 343px | 252px | 27% |

## Verification

Passed:

- `uv run python manage.py check`
- `uv run python manage.py makemigrations --check --dry-run`
- `uv run pytest --ds=config.test_settings tests/test_branch_management.py tests/test_authentication.py tests/test_owner_workspace.py tests/test_onboarding.py -q`: 96 passed before the additional branch regression test.
- `uv run pytest --ds=config.test_settings tests/test_authentication.py::test_device_validation_keeps_selected_branch -q`: 1 passed after the branch retention fix.
- `uv run python scripts/check_ui_layout.py --phase after --compact-forms --output-dir docs/ui-audit/compact-forms`: 154 layout cases; 20 form stress cases, keyboard order/focus, contrast and four complete submit/recovery workflows. Writes only to a temporary SQLite fixture.
- `node --check static/js/owner-forms.js` and `git diff --check`.

Before evidence was recaptured from a detached `a47d960` worktree using the updated capture runner (no product changes in that checkout). Both phases use the same labeled, isolated seed scenario. Clocks and generated record IDs can differ. Screenshot pairs are 1280×900 desktop/light and 390×900 phone/dark, captured full-page; four additional CSS-zoom screenshots and two validation screenshots are retained.

**Not verified:** native browser zoom (CSS zoom 200% and 640px viewport reflow were used), real iOS/Safari/Firefox behavior, screen readers, physical Home Screen setup, real Google consent, production records, RTL translation accuracy, logo file upload/clear interaction and complete app-wide assistive-technology or offline certification.

## Verdict

**Approve for the inspected compact forms and checked domains only.** Whole-app coverage remains partial, as listed in the route/state ledger; native zoom and screen-reader verification remain explicit gaps.
