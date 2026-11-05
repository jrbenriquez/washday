# Undo and offline branch replication

This implementation uses the existing Django services, server-rendered pages and databases. It adds no browser database or service worker. The cloud and hub use the same image; staff connect to their serving app over HTTPS.

## Undo contract

An enrolled device can undo its last reversible operation within six seconds of the server completing it. Supported operations are stage advance/correction, claim/payment, job-linked machine start, self-service start, unload, stock receipt and stock count. A success message offers Undo only when that operation produced a receipt. Other successes never offer an older operation's Undo.

`events/journal.py` records only the rows saved within an explicitly decorated service transaction. `Action` stores per-record before/after values and the original event range. This is not the prototype's whole-application snapshot restore. Undo locks the branch and receipt, checks device/window/last action, compares current rows to the saved result, and checks machine/stage/stock applicability. Expired, repeated, foreign-device and unsafe requests change nothing.

Compensation appends events and inverse stock entries. Original Events, price lines, StockCounts and StockCountLines are retained. Each stock reversal references its original entry and can exist only once. A reversed count remains visible as **Undone** and does not count as the latest completed count. “Used today” includes deduction reversals. Undoing a claim reverses only payment collected by that claim; pre-paid jobs keep their earlier collection. Financial reversal events use the original collection/release day, including paper entries. The correcting action also records its actual occurrence time.

New job creation, access changes and catalog administration do not have Undo receipts. Their existing validation and history remain in place.

## Roles and ownership

- `APP_ROLE=cloud` serves owners and direct-mode staff. Production cloud storage requires PostgreSQL; local development can use SQLite.
- `APP_ROLE=hub` requires `HUB_BRANCH_ID` and local SQLite. New connections use WAL and FULL synchronous writes. This database contains only its assigned branch's operational state, relevant customer/actor identities, and shop configuration.
- Owner and Google account routes are unavailable on a hub. Cloud staff credentials cannot serve a hub-mode branch. Device enrollment is also tied to the branch's writer epoch, requiring re-enrollment at the new address after a mode change.
- Cloud administration of a hub is stored in `ConfigurationAudit`, never in the hub's operational sequence. Shared settings and catalog flow down; operational changes flow up.

Keep clocks synchronized on both machines. Run one worker process per hub. All state, outbox records and write fences are durable across process restarts.

## Replication boundary

`events/records.py` defines the model allow-list. `events/sync/schema.py` validates record identities, shop/branch references, immutable records and import direction before the narrow raw-import path preserves source UUIDs/timestamps. Hub pushes cannot provision cloud devices or update cloud-owned catalog settings. Staff-created SupplyTypes are the one catalog exception. Historical transferred staff are represented on the hub as inactive identities without another branch's usable PIN.

Each Event drains its transaction-local changed rows into an Outbox envelope. Direct writes need no outbox. Every service that can emit operational events must use `@recorded_action`; an unjournaled hub event is rejected. New business services must retain state/event atomicity and avoid unjournaled queryset updates. Protocol 1 accepts additive nullable/defaulted model fields from older queued envelopes without clearing newer existing fields; breaking wire changes require an explicit protocol migration.

The cloud authenticates a random enrolled hub key by its stored SHA-256 digest and binds it to one shop, branch and writer epoch. It stores ordered Inbox receipts with envelope digests. Duplicate UUID/sequence replays must match; conflicting replays fail. Out-of-order envelopes wait durably for gaps. Only contiguous, applied sequences are acknowledged. The worker validates the acknowledgement range and never marks missing events as sent. Dropped replies are safe to retry.

Sent metadata lives on Outbox/Replica, not by rewriting immutable Events. There is no time-based pruning of unsent events. Batches contain at most 500 events. Normal pushes/heartbeats run every 30 seconds; an existing backlog drains in bounded batches without waiting 30 seconds between full batches. Failures use persisted exponential backoff from 30 seconds to 15 minutes, including pull failures.

Settings pull on startup and every five minutes. A version match returns a compact unchanged response; newer configuration applies atomically. Delayed older versions/epochs cannot roll a hub backward. Device configuration/key revisions preserve newer local enrollment while applying later cloud revocations. Used setup codes are never reopened by a delayed pull. Shop logos are authenticated, checksum-checked and cached locally along with packaged fonts/icons/styles.

The transport requires HTTPS outside development loopback and refuses redirects carrying hub credentials. Configure a trusted HTTPS reverse proxy for both serving addresses; the image itself listens on port 8000.

## Offline duplicate supplies

Two offline branches may create different UUIDs with the same name. The cloud keeps both and marks a conflict. Dashboard → **Merge supply types** lets the owner choose the survivor and which settings to keep. Align units first; quantities are not silently converted.

`SupplyAlias` maps the retired identity to the survivor without changing historical Events, stock movements or count lines. Balances aggregate both identities once. Add-on recipes are re-pointed; two recipe lines for the same add-on are combined by quantity. Historical replay against either original UUID remains safe. Configuration pulls carry the alias and archived source to each hub. A merged source cannot be restored as a second active identity.

## Prepare and switch a branch

Do these operator steps after closing. Do not change `Branch.mode` directly or copy a live SQLite database between running writers. Use the branch UUID from the cloud database. Do not use `seed_demo` for real branches.

1. On the cloud, prepare the hub key and its HTTPS address:

   ```sh
   uv run --env-file .env python manage.py hub_mode BRANCH_UUID prepare --hub-url https://hub.example.test
   ```

   The command prints the key once. Put it in the hub's private environment file; never commit it. The cloud stores only its digest.

2. Set the hub environment (example names, not real credentials):

   ```dotenv
   APP_ROLE=hub
   HUB_BRANCH_ID=BRANCH_UUID
   HUB_CLOUD_URL=https://cloud.example.test
   HUB_KEY=the-one-time-issued-key
   DJANGO_DEBUG=0
   DJANGO_SECRET_KEY=an-independent-long-random-secret
   DJANGO_ALLOWED_HOSTS=hub.example.test
   SQLITE_PATH=/data/washday.sqlite3
   MEDIA_ROOT=/data/media
   ```

3. Build the shared image, initialize an empty durable hub database, and bootstrap while the cloud is still the writer:

   ```sh
   docker compose -f compose.hub.yml build web
   docker compose -f compose.hub.yml run --rm web python manage.py migrate --noinput
   docker compose -f compose.hub.yml run --rm sync python manage.py sync_hub --once
   ```

   The web and worker share `hub-data`. A prepared hub cannot accept staff writes. Bootstrap must use an empty migrated database and includes only that branch's current operational state and synced history.

4. Confirm the final cloud sequence after closing. On the cloud:

   ```sh
   uv run --env-file .env python manage.py hub_mode BRANCH_UUID hub --expected-seq FINAL_SEQUENCE
   ```

   Activation refuses if the bootstrap sequence is stale. If staff made more direct writes, make a fresh bootstrap in a new empty hub database before activating. This preserves the old prepared copy for diagnosis rather than overwriting unsent data.

5. Pull the activation and start both local processes:

   ```sh
   docker compose -f compose.hub.yml run --rm sync python manage.py sync_hub --once --force
   docker compose -f compose.hub.yml up -d web sync
   ```

   Re-enroll staff devices using new codes and the hub address. Owner setup invitations use the configured hub URL. A browser must reach the local hub; the hub does not make a phone work when it cannot reach the shop network.

## Return to direct service

1. On the hub, freeze local writes and drain every unsent event:

   ```sh
   docker compose -f compose.hub.yml run --rm sync python manage.py sync_hub --retire
   ```

   The fence is persisted **before** network I/O. A failure leaves the hub frozen with its data retained; reconnect and repeat the command. The cloud accepts retirement only at the exact fully applied final sequence. Stop the ordinary worker during this maintenance operation.

2. On the cloud, use that final acknowledged sequence:

   ```sh
   uv run --env-file .env python manage.py hub_mode BRANCH_UUID direct --expected-seq FINAL_SEQUENCE
   ```

   This refuses an active/non-drained hub, retires its key and advances the writer epoch. Re-enroll devices at the cloud address. The old hub stays frozen even if offline and its retired key no longer authenticates. A later fresh hub cycle uses a new key and an empty bootstrap database.

## Status, diagnostics and recovery

Staff see connection to the serving hub, not the hub's internet connection. An internet outage does not change local staff operation. Owner Dashboard/Live branches show the actual last acknowledged hub contact, a warning after 30 minutes and an as-of view; elapsed machine time does not pretend a stale hub is live.

`/health/` reports process role/readiness of the HTTP process. It does not claim the database has been bootstrapped or that cloud sync is healthy. Inspect Replica cursor/fence/failure/deadline and Outbox sent metadata for sync diagnostics. `sync_hub --once --force` is an explicit operator retry; ordinary restarts preserve backoff. Failures retain data and logs omit keys and record payloads. Credentials and external domains remain operator configuration.

The supplied compose file covers the local web/worker and durable volume. Production TLS, cloud PostgreSQL operation/backups, remote access, nightly updates and hardware recovery remain the separate deployment/operations rollout. Do not expose development fixture bypasses as a deployment.

## Verification and rollout limits

- File-backed SQLite and PostgreSQL pytest suites cover the same branch services; role-parameterized tests cover personal/shared access, loads, PINs, prepaid/unpaid claims and Undo.
- `RUN_CYPRESS=1 uv run python scripts/check_replication.py` uses two private HTTP processes and two temporary databases. It runs lifecycle/count/paper Cypress specs against direct and hub roles, then stops the cloud process while the hub creates jobs and performs Undo. Reconnect compares collections/events, retries, and tests the fenced mode round trip. This is a process-outage simulation, not a physical router/modem cut.
- `uv run python scripts/check_sync_capacity.py` stores 18,000 unsent 1 KiB-payload envelopes across a deterministic 30-day fixture (600/day), checks WAL/no evictions and the 500-event bound. It does not assert a 30-day elapsed soak.
- The Docker `test` target runs the suite inside the image. CI tests native amd64 and arm64 images separately, plus PostgreSQL/SQLite and browser workflows.
- The original four-hour router outage, full-day home dry run, actual shared/personal phones, local Wi-Fi latency, pilot and hardware/UPS gates still require their specified external evidence. Local tests do not certify those rollout criteria. See `.agents/work/undo-offline/` for current verification and visual comparison records.
