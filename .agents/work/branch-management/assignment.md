# Branch management

ID: `branch-management`

Authority: user request to execute `/orchestrate-work for branch management as stated above` following the accepted Branches proposal in this chat. This is a bounded follow-up to existing settings and monitoring, not execution of the entire MVP group.

- AC-01: Replace the Live branches top-level navigation item with Branches. Within Branches, offer Live Branches (default) and Manage Branches. Preserve the existing watch-only live screen, branch selection, and 20-second refresh. Existing live URLs continue working.
- AC-02: Manage Branches lists this shop's branches and supports Add branch and Edit details for name, code, opening/closing hours, and simple/full workflow. New branches default to direct + simple. Allocate internal branch numbers safely without editing existing numbering/counters/history. Include an Edit branch shortcut on the selected live branch.
- AC-03: Branch settings have one editing home in Manage Branches; remove duplicate hours/workflow forms from Settings and Access and devices. Show connection mode, preserve the exact direct outage warning, and refuse unsupported connection-mode changes and simple-mode transitions with open loads. Preserve existing devices, shifts, pricing, and live read-only operations.
- AC-04: Owner-only, tenant-scoped GET/POST with CSRF; foreign IDs return 404. Validate required fields/times and duplicate codes, preserving submitted values and leaving no partial writes on rejection. Accepted changes increment Settings.version and record an owner audit Event atomically.
- AC-05: Branch navigation/list/editor/live are usable at 360px and desktop in light/dark themes, with labelled controls, current-view indication, empty states, and no horizontal page overflow. Verify behavior and affected owner/staff regressions.

Constraints: existing Django/templates/HTMX stack, dependencies and tenant/event patterns. No deployment, real external effects, branch deletion, hub provisioning/migration, or unrelated MVP completion. Existing branch numbers are immutable internal identifiers; new numbers are allocated within the shop. Local SQLite tests/browser fixtures establish development acceptance; no claim of PostgreSQL concurrency qualification or physical-device acceptance.

Baseline: fresh origin/main 312eb367506c76b12415b7674c3c12a0336ae734, fetched during this invocation; clean original branch work preserved. Worktree /workspace/washday, branch codex/branch-management. No previous branch-management work/state exists. Existing MVP and settings attempt histories remain unchanged.
