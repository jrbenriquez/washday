# Prove the hub kit survives unattended operation and power loss

## Title and ID
`washday-mvp-hardware` — Home N100/UPS/router qualification (rollout step 5).

## Source
[PRD](../../reference/docs/PRD.md) §8 offline/UPS/restore targets; §9 rollout step 5, laptop limitations and checklist line 551; §10 hardware/network/setup.

## References
[Package README](../../reference/README.md), [paper sheet](../../reference/docs/paper-job-sheet.pdf) failure procedure, [preview](../../reference/prototype/index.html) for the existing screens during dry run, [brand](../../reference/img/logo-header.png), [shared constraints](README.md#shared-execution-constraints).

## Desired outcome
One actual hub kit is qualified at home before any branch moves to hub mode, proving what a laptop cannot demonstrate.

## Dependencies
`washday-mvp-hub-operations`: tested role/sync/update/backup/restore procedures and full-day laptop dry run evidence. External: one Intel N100 hub with SSD, UPS, router, Ubuntu/Docker/Tailscale, power-cut access, actual shared/personal devices and seven days of observation. Purchase/physical work remains owner-controlled.

## Acceptance criteria
- **AC-01:** Real kit is prepared at home using Ubuntu Server, Docker, Tailscale and branch configuration; network has client/AP isolation off, devices on main not guest Wi-Fi, reserved hub address/local name, and hub/router on UPS. Ethernet is preferred; if layout requires Wi-Fi, saved network reconnects after router restart and placement avoids metal equipment interference.
- **AC-02:** Repeat the sample staff dry run/internet cut on actual N100 hardware with shared/personal devices, not merely emulated amd64. No event/state loss and both devices remain in step; real-hub latency meets pages **under 200 ms**, actions **under 300 ms** on local Wi-Fi.
- **AC-03:** Kit runs **7 days unattended**. After a controlled power cut it restarts automatically and resumes branch service/sync without manual app startup; record event reconciliation and boot/sync evidence.
- **AC-04:** UPS sustains **both hub and router at least 2 hours** under the measured operating load, devices on their batteries. An estimated VA rating or laptop battery does not count as runtime proof.
- **AC-05:** A scheduled overnight image update applies after closing on the real hub and resumes service/sync, with previous-version queued events accepted. Snapshot schedule/retention and Tailscale support access are exercised on Ubuntu hardware.
- **AC-06:** Results identify exact tested hub/SSD/UPS/router/device models, configuration, dates, latency/runtime/power recovery/update evidence and unresolved failures; owner/JR review confirms kit readiness before moving it to a branch.

## Constraints
[Shared constraints](README.md#shared-execution-constraints); staged procurement: one hub kit first (~₱16,300 source estimate), remaining hubs only after pilot success. No requirement to buy a particular example retail brand; preserve specified N100/SSD/UPS capability and observed targets. SIM router is hub-only option where no internet line; reliable existing router can be reused. No thermal printer in version 1.

## Out of scope
Live branch pilot and additional/spare hubs: `washday-mvp-hub-rollout`; software defects require bounded correction plus affected regressions in their owning outcomes.

## Verification notes
Keep an actual seven-day log and controlled tests for router internet cut, power restoration, UPS exhaustion/runtime, unattended update and remote access. Retain Event before/after reconciliation. Do not mark the outcome PASS based on laptop evidence, simulated power commands or unrun procedures.

## Open questions/blockers
Blocked by hub-operations evidence, owner-provided hardware/physical access and seven elapsed days of observation.
