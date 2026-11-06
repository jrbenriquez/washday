# UI audit and visual comparisons

This pass simplifies the shared staff and owner interface while retaining the existing forms, actions, explanations, status labels and workflows. It builds on `main` at `2ce71d3` (including the claim/payment/PIN modals).

## Find the changes

Open a screenshot below, or open [the comparison gallery](gallery.html) locally to see both versions together. Desktop captures are **1280 px / light**; phone captures are **390 px / dark**. Both sides use the same isolated demo scenario. Clock times and generated record IDs can differ between runs.

| Screen | What improved | Desktop | Phone |
| --- | --- | --- | --- |
| Dashboard | Cards use both columns; report fields and export share a row; mobile metrics form a 2×2 grid. Alerts use separators instead of nested tinted boxes. | [Before](before/dashboard-1280-light.png) · [After](after/dashboard-1280-light.png) | [Before](before/dashboard-390-dark.png) · [After](after/dashboard-390-dark.png) |
| New job | Consistent section spacing, lighter control borders, clearer heading hierarchy and quieter summary separators. | [Before](before/intake-1280-light.png) · [After](after/intake-1280-light.png) | [Before](before/intake-390-dark.png) · [After](after/intake-390-dark.png) |
| Jobs board | All five fixture stages fit at desktop width; cleaner column surfaces and card spacing retain payment, age, stage and machine context. | [Before](before/board-1280-light.png) · [After](after/board-1280-light.png) | [Before](before/board-390-dark.png) · [After](after/board-390-dark.png) |
| Settings | Branch and machine settings share a column; mobile catalog recipes, prices and actions have separate space; stage actions keep their text on one line. | [Before](before/settings-1280-light.png) · [After](after/settings-1280-light.png) | [Before](before/settings-390-dark.png) · [After](after/settings-390-dark.png) |
| Supplies | Consistent heading/card spacing, fewer incidental paragraph gaps and left-aligned ledger links. | [Before](before/supplies-1280-light.png) · [After](after/supplies-1280-light.png) | [Before](before/supplies-390-dark.png) · [After](after/supplies-390-dark.png) |
| Branches | Aligned name/code row and a separated action area make branch details easier to scan. | [Before](before/branches-1280-light.png) · [After](after/branches-1280-light.png) | [Before](before/branches-390-dark.png) · [After](after/branches-390-dark.png) |
| Staff | Shared form spacing and a two-column tablet card layout improve use of available width. | [Before](before/staff-1280-light.png) · [After](after/staff-1280-light.png) | [Before](before/staff-390-dark.png) · [After](after/staff-390-dark.png) |
| Machines | Shared typography and neutral surfaces clarify machine states and supporting text. | [Before](before/machines-1280-light.png) · [After](after/machines-1280-light.png) | [Before](before/machines-390-dark.png) · [After](after/machines-390-dark.png) |
| Access and devices | Consistent form/card rhythm and compact owner navigation. | [Before](before/access-1280-light.png) · [After](after/access-1280-light.png) | [Before](before/access-390-dark.png) · [After](after/access-390-dark.png) |
| Owner login | Shared palette, headings and authentication-card spacing. | [Before](before/login-1280-light.png) · [After](after/login-1280-light.png) | [Before](before/login-390-dark.png) · [After](after/login-390-dark.png) |
| Stage dialog | Shared type, surface and inset spacing; close, Escape and focus return remain available. | [Before](before/stage-dialog-1280-light.png) · [After](after/stage-dialog-1280-light.png) | [Before](before/stage-dialog-390-dark.png) · [After](after/stage-dialog-390-dark.png) |

## Shared design decisions

- Use neutral light/dark canvases and reserve indigo, teal and semantic colors for selection, branding and statuses.
- Use Figtree for page and section headings, retaining the condensed brand and monospaced numbers.
- Align desktop page insets at 24 px, phone insets at 16 px, and use consistent card and field gaps.
- Replace the owner navigation capsule with a full-width tab row. Phones show all six destinations in two rows of three, with a visible selected state.
- Preserve wide data tables in their existing horizontal scroll containers so their labels, units and actions remain available. Keep printed stubs outside the screen-only layout adjustments.

## Scope and validation

The capture script checks 19 staff/owner routes at **360, 390, 768 and 1280 px**, in **light and dark** themes (152 layout cases), plus two signed-out login cases. It also checks catalog-cell collisions, desktop board fit, and dialog dismissal/focus return. See [before results](before/checks.json) and [after results](after/checks.json).

Routes include dashboard, live branches, branch management/editor, staff, machine administration, settings, catalog editor, count history, access/devices, intake, paper intake, board, list, job history, timeline, claim stub, machines and supplies.

The application changes are limited to CSS tokens/styles and dashboard/settings layout wrappers. URLs, form methods/fields, JavaScript, pricing, permissions, workflow transitions and data models are unchanged by this PR.

Validation passed: **170 Django tests**, catalog editing (including autosave and the JavaScript-free fallback), branch creation/editing and timed refresh, and the current modal workflow probe (claim/payment, PIN, intake, catalog edits, export and theme switching). [Validation results](validation.json) also record two older probes with outdated screen assumptions; the current branch/catalog/modal probes provide the browser acceptance checks for this change.

### Reproduce

```sh
uv sync --locked
uv run python scripts/check_ui_layout.py --phase after
EVIDENCE_RUN=my-ui-review uv run python scripts/check_owner_settings_browser.py
EVIDENCE_RUN=my-ui-review uv run python scripts/check_branches_browser.py
EVIDENCE_RUN=my-ui-review uv run python scripts/check_prototype_parity.py
uv run pytest --ds=config.test_settings -q
```

The capture script creates a temporary SQLite database, seeds labeled fixtures, creates a private fixture owner session and starts a loopback server. It expects Chromium at `/usr/bin/chromium` and does not alter your development database. To reproduce the before images, copy the capture script into a checkout of `2ce71d3` and run it there with `--phase before`. Regenerating evidence replaces the corresponding phase's files.

Choose a fresh `EVIDENCE_RUN` for the existing browser probes. To view the comparison gallery through a local server, run `uv run python -m http.server 8765 --bind 127.0.0.1 --directory docs/ui-audit` and open `http://127.0.0.1:8765/gallery.html`.
