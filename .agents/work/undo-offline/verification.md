# Integrated verification: Undo and offline replication

Inspected the integrated dirty workspace, not a worker branch. Exact source, fixtures, lockfiles, prototype and configuration are identified by `final-source-manifest.json`. The only delta from the initial freeze is a screenshot-harness fixture query moved outside Playwright's async loop; no product code changed during verification. Historical diagnostic logs are retained separately and do not establish a pass.

Environment: managed Linux amd64, Python 3.13/uv locked dependencies, file-backed SQLite, PostgreSQL 17 in an isolated fixture container, system Chromium/Cypress 16.2.1, local two-process HTTP fixture with separate SQLite databases. Test passwords/identities are development fixtures. No production deployment or real staff data was used.

Evidence:

- V1: `uv run pytest --ds=config.test_settings -q`: **136 passed**, file-backed SQLite; `evidence/pytest-sqlite.txt`.
- V2: same complete suite using PostgreSQL 17: **136 passed**; `evidence/pytest-postgres.txt`.
- V3: `RUN_CYPRESS=1 uv run python scripts/check_replication.py`: three Cypress specs passed in each role, real HTTP bootstrap, stopped cloud, three offline jobs, stock receipt/Undo, reconnect with matching collections, duplicate worker replay, fenced direct/hub/direct round trip. Reconnect-to-owner 1.887s in this loopback fixture. `evidence/browser-http.txt`, `evidence/cypress-{direct,hub}.txt`, `evidence/replication.json`.
- V4: `uv run python scripts/check_sync_capacity.py`: 18,000 unsent envelopes (30 days × 600/day with 1KiB event payload), SQLite WAL, approximately 69 MB, zero retention evictions. Deterministic capacity fixture, not an elapsed-time soak. `evidence/capacity.json`.
- V5: `manage.py check`, `makemigrations --check --dry-run`, JavaScript syntax and `git diff --check` passed. New schema migrations are additive; no migration drift.
- V6: opened all 12 paired component comparisons at 390/1280 in light/dark; inspected hierarchy, colors, typography, wrapping, alignment and navigation clearance. `visual-comparison.md` and paired PNGs.
- V7: optimized shared Docker test image built successfully; complete in-image suite **136 passed** as the non-root app user; `evidence/pytest-image.txt`. Native amd64/arm64 tests and browser/PostgreSQL/SQLite jobs are configured in CI; native arm64 cannot be run by the local amd64-only builder. Consult the PR's checks for subsequent CI results.

| Outcome / criterion | Status at local verification | Basis / remaining evidence |
|---|---|---|
| people AC-06 | PASS | V1–3, V6: clock boundaries, device binding, stale-state refusal, exact success receipt, duplicate refusal, stock/count/load/payment compensation, original immutable history and signed financial projection. |
| people AC-08 (assigned Undo/regression scope) | PASS | V1–3, V6: existing guarded routes, tenant isolation, code/PIN/shift policies, actor attribution and financial/history regressions. Physical installation persistence remains the separate cloud-release acceptance. |
| sync AC-01 | PASS | V1–3, V7: role fences, assigned branch, atomic event/state/outbox, WAL and PostgreSQL coverage; direct needs no outbox. |
| sync AC-02 | PASS | V1–3: authenticated bound keys, typed 500-event limit, gap/reorder/replay conflicts, persistent retry/backoff, dropped response and contiguous cursor tests. |
| sync AC-03 | PASS | V1–3: version/epoch checks, startup/five-minute pull, atomic catalog, tenant scope, delayed enrollment/code/revocation cases and serving-hub connectivity. |
| sync AC-04 | PASS | V1–2: both UUIDs retained, explicit owner survivor/settings selection, same-unit requirement, recipes and alias balances, immutable histories and safe replay. |
| sync AC-05 | PASS | V1–3: bootstrap boundaries, stale-bootstrap refusal, epoch re-enrollment, persistent freeze/drain and writer fencing; real HTTP round trip. |
| sync AC-06 | INCONCLUSIVE locally | Complete backend suites, role workflows and both-role Cypress passed, including replicated owner totals. Native arm64 image validation is delegated to PR CI and needs its result before multiarchitecture acceptance. |
| sync AC-07 | INCONCLUSIVE | V3–4 establish protocol reconnect and representative 30-day capacity; four-hour physical router/modem outage with personal/shared devices unavailable. |
| sync AC-08 | INCONCLUSIVE | V3/V6 establish loopback owner freshness, stale/as-of/alert presentation and local assets. Actual Wi-Fi page/action latency targets remain unmeasured. New inferred merge form lacks exhaustive browser visual validation. |
| sync AC-09 | INCONCLUSIVE | Full-day home dry run with JR's phone and a second device unavailable. |

Overall assigned people slice PASS; original people outcome is not certified complete by this partial scope. Original sync outcome INCONCLUSIVE due external acceptance evidence, with no observed local product failure. No physical pilot, router outage, laptop/N100 operation, UPS or full-day qualification is claimed. Previous authentication and prototype parity reports are historical; relevant services and changed components were rerun above.

Initial diagnostic failures: environmental disk exhaustion during an earlier parallel image/database attempt; discarded as acceptance evidence, followed by clean full runs with sufficient disk. Screenshot harness async-context error corrected without changing application behavior; complete browser run rerun. The PostgreSQL suite exposed nullable outer-join row locks during implementation; corrected locking of base rows was verified in V2.

Next: commit/push/open PR under the user's authorization; inspect all CI including native arm64. Then perform the documented physical rollout tests before production rollout. Preserve implementation budgets: people 2/3, sync 1/3. No new code retry is justified by unavailable hardware evidence.
