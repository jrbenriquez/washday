# Requested implementation: Undo and offline replication

User explicitly requested /orchestrate-work implementation of these two remaining gaps on a new branch from latest main, with full tests, commit, push and an open PR. No deployment or merge is requested for this PR.

Authority: outcomes/washday-mvp/washday-mvp-people.md AC-06 and Undo-related AC-08; outcomes/washday-mvp/washday-mvp-sync.md AC-01–09; reference/docs/PRD.md; accepted authentication and machine-start amendments. Preserve original criteria.

Implementation is authorized now; physical direct pilot, router/device timing, 4-hour outage, full-day dry run and multiarchitecture hardware evidence remain release prerequisites, not locally certified outcomes. Keep unavailable checks INCONCLUSIVE and avoid presenting a local protocol test as a physical acceptance test.

Design: immutable compensating events with per-record change checks; authenticated ordered replication with durable acknowledgements, versioned configuration and fenced mode changes. Keep existing Django/HTMX/services and use DRF only for sync endpoints. No browser database or service worker.

Execution: one coordinator, sequential implement/verify/recalibrate. Existing attempt counts and historical outcome records are retained. Previous group coordinator is this same chat, has no active invocations, and selected work is explicitly handed to this scoped invocation.
