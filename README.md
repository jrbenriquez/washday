# Washday

Local implementation of the accepted Washday outcomes. Python 3.13, Django 6, server templates + locally served HTMX; SQLite development, PostgreSQL configuration via `PGDATABASE`/`PGHOST`/`PGPORT`/`PGUSER`/`PGPASSWORD`.

```sh
uv sync --locked
uv run python manage.py migrate
uv run python manage.py seed_demo
```

The last command prints a run command with the generated `DEV_BRANCH_ID` and `DEV_STAFF_ID`. Use it to start the app on `127.0.0.1:8000`. Open http://127.0.0.1:8000/jobs/new/ (or `?paper=1`). All fixtures and operational prices are explicitly DEMO; only the real brand and PRD Rush fee are prescribed values. Run `uv run pytest` for the implemented behavior.

Development branch resolution comes exclusively from server environment settings and is disabled when `DJANGO_DEBUG=0`. Device enrolment, owner authentication and deployment are later outcomes; this milestone must only run locally. An unconfigured browser gets 404, rather than access to an arbitrary shop. Nothing here constitutes production/device/pilot acceptance.

Assets are local, including fonts and HTMX. Font sources, SHA-256 digests and OFL licences are in `static/fonts/`; HTMX 2.0.8 is vendored with its licence. Tokens were copied from the supplied preview. Pricing is computed only on the server, including live summaries. Claim stubs use the device print dialog.

Outcome definitions remain in `outcomes/washday-mvp/`. Durable state, phase handoffs and evidence are in `.agents/work/`; resume using `orchestrate-work for outcomes/washday-mvp` without resetting saved attempts.

For a quick local start after seeding, `uv run python scripts/run_demo_server.py` selects only the labelled DEMO branch. `uv run python scripts/set_demo_mode.py full` exposes the machine flow; use `simple` to return to the default. Start job-linked loads on the Jobs board. Machines provides monitoring, Unload, and paid self-service without a Job.

Browser probes in `scripts/check_*_browser.py` require that server. Intake/progression probes use simple mode; machine probes use full mode and idle W1/D1. `npm ci && npm run test:e2e` runs the required Cypress lifecycle once the Cypress binary is installed. If the normal binary download host is unavailable, run `python3.13 scripts/install_cypress_from_image.py`. It installs the Linux amd64 Cypress runtime and Xvfb from SHA-256-verified layers of the official `cypress/included:16.2.1` image through the configured proxy, without pulling unrelated browsers. Keep `$HOME/.local/bin` on PATH. `npx cypress verify` confirms the installation. The lifecycle and full/partial stock-count Cypress suites have now both passed.
