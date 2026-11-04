# Latest main integration

Merged main 312eb367506c76b12415b7674c3c12a0336ae734 (PR8: staff-management/PIN owner routes) cleanly into the resilience branch. Source is identified by integrated-main-manifest.json; previous manifests/reports remain historical snapshots.

Independent regression: `uv run pytest --ds=config.test_settings -q` **148 passed**, including the 12 newly merged owner tests; evidence/pytest-integrated-main.txt. Django check, migration drift and whitespace checks passed again. No custom product fix was required for integration.

Reviewed the eight changed source/test files: owner staff/settings context helpers, their templates, existing authentication browser harness and owner tests. The Undo journal, sync protocol, counter/machine/supply services, shared CSS/JS, dashboard/live templates and dashboard/live functions are unchanged. Prior paired component visuals and protocol/capacity evidence therefore remain applicable to those unchanged components. The full original report remains in verification.md; no physical evidence has been added.

Final PR CI runs the full expanded suite on SQLite/PostgreSQL, native amd64/arm64 images, and both-role Cypress/HTTP recovery against the integrated source. PR: https://github.com/jrbenriquez/washday/pull/11 (checks are the authoritative subsequent native CI evidence). No deployment or merge is requested.
