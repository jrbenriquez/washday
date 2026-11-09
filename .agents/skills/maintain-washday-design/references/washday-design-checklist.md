# WashDay design checklist

Use this as a map to the current app, not a frozen route list or a substitute
for the upstream skills. Discover additions and removals from current source.

## Project conventions

- Django-rendered HTML, native forms and controls, plain CSS and JavaScript.
- Shared design tokens: `static/css/tokens.css`.
- Shared layout and controls: `static/css/app.css`, `templates/base.html`,
  `templates/auth_base.html`, `templates/brand.html` and `static/js/app.js`.
- Onboarding: `owner/onboarding.py`, `templates/owner/onboarding*.html`,
  `static/css/owner-onboarding.css` and `static/js/owner-onboarding.js`.
- Product terminology and flows: `README.md`, `docs/authentication.md` and
  `docs/offline-and-undo.md`; inspect other relevant docs when present.
- Prior visual evidence: `docs/ui-audit/`. Treat it as comparison material,
  never as proof of the current working tree.

Keep the existing Figtree/Saira Condensed/JetBrains Mono roles and semantic
color tokens. Do not borrow a border color for text or introduce a different
font or color system to fix a local screen. Measure actual light/dark contrast,
including input boundaries, focus rings, secondary text and numbered badges.

## Whole-app inventory starting points

Read `config/urls.py`, `owner/urls.py` and their current views/templates. Include:

- Entry/sign-in and device installation/enrollment, unavailable/invitation states.
- Owner onboarding, catalog defaults, custom rows, validation, removal/Undo,
  save confirmation, optional setup and the prefilled Add device handoff.
- Owner dashboard, live branches, branch management, hours and workflow settings.
- Staff/PIN management, device assignment and access, invitation and revoke flows.
- Catalog/services, piece items/sizes, fees/add-ons, supplies and shop branding.
- Counter intake, weight/pricing, customer selection, payment/PIN prompts and stubs.
- Job board, stage progression/corrections, claim/release, job history and pagination.
- Machines, loads, self-service and simple/full workflow differences.
- Supply receipt/count/request flows, stock history, alerts and Undo.
- Staff sessions, assigned personal phones, shared devices and operating-hours states.
- Reports/exports and print views; operator admin/impersonation where accessible.
- Cloud/direct versus hub/offline UI, stale-data feedback, synchronization and recovery.

Do not confuse aliases or POST-only action endpoints with separate screens.
Do not treat APIs/health endpoints as visual screens. External Google consent,
physical Home Screen behavior and inaccessible operator/production screens must
be named as boundaries or unverified coverage, not silently counted as reviewed.

## Compact and functional

- Group identifying fields with their billing unit and price; use shared edges
  and sensible content widths instead of full-width stacked fields everywhere.
- Put related limits side by side only while labels, values and controls fit.
- Prefer space and existing surfaces to repeated nested cards and separators.
- Keep one primary action, clear secondary controls and an obvious next step.
- Make optional piece items explicit. Removals should retain entered values and
  offer Undo; removing all services must leave a recovery path.
- Keep visible labels and inline errors. Focus a useful recovery cue on failed
  submit; preserve entered values and formset indices through validation.
- Name icon actions by their effect. Native buttons must work with keyboard,
  retain visible focus and have distinct, usable hit areas.
- Avoid hover-only actions and animation-only feedback. Respect reduced motion;
  use the exact motion values from better-ui when introducing its recipes.
- At 320px and larger, prevent clipped actions and horizontal scrolling. Let
  labels grow, keep mobile inputs at 16px and avoid sticky chrome hiding focus.
- Check logical spacing/RTL, dark theme, long content and 200% zoom. Preserve the
  full value of editable text; do not mistake input scrolling for lost content.

## Verification starting points

Discover and read a script before running it: some scripts write to seeded
development fixtures. Use isolated databases/fixtures and never production data.

- `uv run python manage.py check`
- `uv run python manage.py makemigrations --check --dry-run`
- `uv run pytest --ds=config.test_settings -q` when broad regression coverage fits.
- Relevant focused tests in `tests/`, browser probes in `scripts/`, and Cypress
  workflows in `cypress/` as applicable to the resolved scope.
- `git diff --check` and JavaScript syntax checks for changed scripts.

A source-only review cannot establish rendered layout, keyboard usability or
visual parity. A screenshot alone cannot establish correct pricing, access,
submission or offline behavior. Record what each kind of evidence proves.
