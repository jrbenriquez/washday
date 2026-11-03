# Recover and update a hub without sacrificing branch history

## Title and ID
`washday-mvp-hub-operations` — Backups, spare restore, nightly updates and remote access (milestone 5 completion).

## Source
[PRD](../../reference/docs/PRD.md) §3 packaging/remote access/bootstrap; §8 Offline, Hub failure, Data safety, Tenant isolation, Security, Updates; §9 milestone 5; §10 setup steps 2, 7–8.

## References
[Package README](../../reference/README.md), [paper outage sheet](../../reference/docs/paper-job-sheet.pdf), [preview](../../reference/prototype/index.html) existing connection/as-of presentation only, [brand](../../reference/img/logo-header.png), [shared constraints](README.md#shared-execution-constraints).

## Desired outcome
A branch can recover synced data on a replacement hub and safely receive after-closing software updates, with recoverable snapshots and restricted remote support.

## Dependencies
`washday-mvp-sync`: role/image/bootstrap/outbox and both-architecture evidence pass. External: cloud backups/access, Tailscale account/network, Ubuntu target for operational configuration; actual physical tests are owned by hardware.

## Acceptance criteria
- **AC-01:** Hub runs SQLite WAL on SSD with a **nightly local snapshot retaining 7**. Cloud daily PostgreSQL backups retain **30** (regress cloud-release). Snapshot/restore procedures preserve immutable events and usable state under concurrent/restarting service.
- **AC-02:** A new/spare hub restores its assigned branch's **all synced events/current state from cloud in under 30 minutes** and resumes branch service/sync. It receives no another-branch operations or another-shop data. Restore evidence explicitly distinguishes cloud-synced events from unsent events unavailable after a failed hub; no invented guarantee of recovering destroyed unsynced local data.
- **AC-03:** Staff can use the paper sheet during hub failure and reconcile once the spare is reachable; received/payment/claim sheet times and P uniqueness survive the restore/re-entry workflow.
- **AC-04:** Hubs pull the new Docker image **nightly after branch closing time**, restart and resume sync. Schema migrations accept events from the **previous version**; queued older-version events sync without loss or duplicate side effects after upgrade. Updates do not require replacing frameworks or database engines.
- **AC-05:** Support reaches hubs remotely only via Tailscale; no public hub SSH/app support endpoint bypasses that boundary. Local staff Wi-Fi access continues normally. Ubuntu/Docker/Tailscale/branch ID/environment, snapshot paths and recovery/update procedures are reproducible for a spare hub.
- **AC-06:** Tests/recovery drills check tenant-scoped backup/bootstrap restore, restart with queued events, prior-version schema/event compatibility and branch enrolment after replacement. Logs/timing/procedures identify what was exercised on laptop versus actual Ubuntu hardware; automated configuration success is not a physical uptime claim.

## Constraints
[Shared constraints](README.md#shared-execution-constraints); maintain one amd64/arm64 image, branch ID pinning and settings ownership. Keep user-owned secrets out of documentation and exports. Tests do not authorise production failure drills without a subsequent execution request/access. Source hardware budget/examples are purchase guidance, not a software dependency upgrade requirement.

## Out of scope
UPS ≥2 hours, seven-day unattended real-hardware and physical power-cut validation: `washday-mvp-hardware`; live two-week pilot and spare shipped to branches: `washday-mvp-hub-rollout`.

## Verification notes
Document and run snapshot restore, empty replacement bootstrap with timer, cross-shop/branch isolation probes, prior-version event replay across migration and scheduled update after closing. Reconcile event sets/stock/payments before/after. State measured duration and environment for every recovery/update claim; keep real hardware checks pending until exercised.

## Open questions/blockers
Blocked by `washday-mvp-sync` evidence and external cloud/Tailscale/Ubuntu access. No additional functional decision.
