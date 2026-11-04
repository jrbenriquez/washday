# Prototype UI alignment

- Type: implementation
- Outcome: user-requested prototype UI alignment (no formal outcome ID)
- Criteria: shared typography/navigation and intake controls should follow `reference/prototype/index.html`; existing intake workflows should remain usable.
- Status: READY_FOR_VERIFICATION
- Changes: restored prototype SVG rail icons and theme control, logo proportions, section typography, native-input service chips and payment segments, weight display, compact summary/total, and piece/add-on grouping. GCash reference appears when GCash is selected. Default service follows displayed catalog order. Fixed decimal keypad entry/backspace. Browser probe supports installed Playwright Chromium and configurable origin.
- Assumptions: development fixture labels/prices stay authoritative; the screenshot's prototype-only owner/branch switching and sync simulation are not live staff features.
- Gaps: visual comparison on the user's actual browser/display remains outstanding; no claim of whole-app pixel parity.
- Blockers: []
- Next: review the updated intake and shared shell against the prototype in the user's browser, including its zoom level.

## Evidence

### I1 — Python regression suite
- Action: `uv run pytest -q`
- Context: macOS, project uv environment, working-tree changes listed above.
- Observation: 93 passed, 1 skipped (existing in-memory SQLite concurrency skip).
- Reference: terminal output from this session.

### I2 — Django and diff checks
- Action: `uv run python manage.py check`; `git diff --check`.
- Observation: no Django issues or diff whitespace errors.
- Reference: terminal output from this session.

### I3 — Browser intake and persistence probe
- Action: `BASE_URL=http://127.0.0.1:8001 EVIDENCE_RUN=prototype-polish-20261104 uv run python scripts/check_intake_browser.py`.
- Context: Playwright Chromium, labelled DEMO SQLite fixtures; 360/390/1280px, light/dark.
- Observation: six intake rendering cases and end-to-end flows passed; no external requests or JavaScript errors. Checks include decimal keypad/backspace, keyboard payment selection, GCash visibility, creation, search/select, pieces-only, paper reconciliation/duplicates, printing and theme persistence.
- Reference: `browser.json`, `intake-*.png`, `stub-*.png`, `stub-print.pdf` in this directory.

### I4 — Shared shell smoke checks
- Action: visited Jobs board/list/history, Supplies and owner login at 390/1280px in light/dark themes.
- Observation: 20 cases returned HTTP 200 without horizontal page overflow or JavaScript errors.
- Reference: terminal output from this session.
