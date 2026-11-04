# Scheduled Google Drive exports

Implemented on `feature/google-drive-scheduled-exports`, based on `origin/main`.
Owners can connect a Google account, choose an existing writable folder using
Google Picker or create a new folder in My Drive, and export every 1–365 days at
a selected local time and IANA timezone. All branches of the owner's shop are
included. Each shop has one shared connection and schedule; any active owner of
that shop can administer it. Connecting Drive is separate from signing in, and
the connected Google account can differ from the login account.

## What to set up to test

1. In Google Cloud Console, select or create a project. Enable **Google Drive API**
   and **Google Picker API** (Picker is only needed to choose existing folders).
2. Configure Google Auth Platform / OAuth consent with the appropriate audience.
   For an external app in Testing, add both the owner login email and the Drive
   account email as test users. Request `openid`, `email`, and
   `https://www.googleapis.com/auth/drive.file`. This limited file scope lets the
   app access folders/files created by the app or explicitly selected in Picker.
   An arbitrary folder ID pasted into an API request does not grant permission.
3. Create an OAuth client of type **Web application**. Add these authorized
   redirect URIs for local testing:

   ```text
   http://localhost:8000/accounts/google/login/callback/
   http://localhost:8000/owner/drive-exports/callback/
   ```

   Use the first URI for the existing owner sign-in client; use the second for
   the Drive client. They may be the same OAuth client. Add
   `http://localhost:8000` as an authorized JavaScript origin. Use exact HTTPS
   origins/callbacks for deployed environments; localhost and 127.0.0.1 differ.
4. To choose existing folders, create an API key in the **same project**. Restrict
   it to Google Picker API and your application's HTTP referrers, e.g.
   `http://localhost:8000/*`. Copy the project's **numeric project number** as
   `GOOGLE_DRIVE_APP_ID` (not its text project ID). This browser API key is public
   by design; restrict it. Never put the OAuth client secret in JavaScript.
5. Copy `.env.example` to `.env` if needed and set:

   ```dotenv
   GOOGLE_CLIENT_ID=<owner-sign-in-client-id>
   GOOGLE_CLIENT_SECRET=<owner-sign-in-client-secret>
   # Optional separate Drive client; otherwise the login client is reused.
   GOOGLE_DRIVE_CLIENT_ID=<drive-web-client-id>
   GOOGLE_DRIVE_CLIENT_SECRET=<drive-web-client-secret>
   GOOGLE_DRIVE_REDIRECT_URI=http://localhost:8000/owner/drive-exports/callback/
   GOOGLE_DRIVE_TOKEN_KEY=<generated-fernet-key>
   GOOGLE_DRIVE_PICKER_API_KEY=<restricted-browser-api-key>
   GOOGLE_DRIVE_APP_ID=<numeric-google-cloud-project-number>
   ```

   Generate a key with:

   ```bash
   uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
   ```

   Keep this stable and secret, with exactly the same value on the web server
   and worker. Tokens are encrypted in the database with this key. Losing or
   changing it requires reconnecting Drive. Store the production key in your
   secret manager. Do not commit `.env`.
6. Install and migrate, then allow-list the owner (see the main README for seeding
   a local shop and the existing sign-in flow):

   ```bash
   uv sync
   uv run --env-file .env python manage.py migrate
   uv run --env-file .env python manage.py allow_owner you@example.com --shop-code DEV-ONLY
   uv run --env-file .env python manage.py runserver
   ```

   `DEV-ONLY` must be the code of an existing test shop. The `.env` file is loaded
   by `uv --env-file`, not automatically by Django. Use the same database settings
   for all commands and the web server.
7. Sign in at `http://localhost:8000/owner/login/`. Open **Drive exports** in the
   owner navigation. Click **Connect Google Drive**, approve background file
   access, then choose a folder or create `WashDay test reports`.
8. Leave automatic exports paused and click **Queue test export now**. In another
   terminal run:

   ```bash
   uv run --env-file .env python manage.py run_drive_exports
   ```

   Refresh the page. Expect a `success` run with a Drive link. Open it and check
   `manifest.json`, `snapshot.json`, and the CSV files. These are actual exports;
   a shop with no activity still produces CSV headers and reference records, so
   no dummy file is needed. A failed or running folder is labelled incomplete.
9. For the recurring test, choose `1` day, a time a few minutes ahead, and
   `Asia/Manila`. Enable automatic exports and save. Run the command after the
   displayed due time, or install the scheduler below. Running it again should
   create no duplicate completed export. Confirm that the next due time moves
   to the next local day.

## Install the recurring server task

The Django command performs one bounded tick and exits; the web server does not
start a background thread. Configure cron or your hosting platform's scheduled
job to invoke it **every minute** against the same database and environment as
the web app. A Linux cron example (replace all paths with your deployment paths):

```cron
* * * * * cd /srv/washday && /usr/local/bin/uv run --env-file /srv/washday/.env python manage.py run_drive_exports --limit 20 >> /var/log/washday-drive-exports.log 2>&1
```

Use the actual `uv` executable path from your deployment. The scheduler timezone
does not matter: due times are stored as UTC instants. The chosen report timezone
controls dates and recurrence. Repeated local times at a DST fall-back run once;
nonexistent times at a spring-forward normalize forward. The scheduler tick may
start a minute or more after the selected time, depending on tick frequency and
queue size. A tick processes at most 20 shops by default, one run per shop. Keep
this worker on the authoritative server; there is no offline hub sync yet.

A database lease prevents overlapping workers from claiming the same shop.
An abandoned lease can be reclaimed after one hour. Do not configure an external
job timeout longer than one hour. Failed runs retry after five minutes, reuse the
same dated folder and update existing report files. The next recurring date only
advances after all files upload successfully. After downtime, overdue scheduled
dates catch up one per shop per tick. These reports read the data available at
the time they run; they cannot reconstruct old point-in-time database snapshots.

Editing the schedule restarts it at the next selected wall-clock time and retires
unfinished runs from the old schedule. A test export does not move the schedule.
Settings changes are blocked while a worker holds the shop's lease. Disconnecting
removes the local credentials and cancels unfinished runs; existing Drive copies
remain. To revoke Google's grant too, remove the application's access from the
Google account's third-party connections page. Removing the owner who connected
Drive pauses worker access until an active owner reconnects it.

## Files and report period

Each run creates a child folder named like:

```text
2026-11-04 - SHOP-CODE - 1a2b3c4d/
```

The date comes from the scheduled instant in the selected timezone; the suffix
separates test runs and shops sharing the same parent. The folder contains:

- **24 CSVs:** jobs and job lines; machine loads; stock entries, counts and count
  lines; supply requests; events; shifts; and current branch, catalog, customer,
  staff, device, machine and shop-settings reference tables. The manifest labels
  each table as daily activity or current reference. Job activity includes
  receipts/payments/claims/readiness and jobs mentioned by that day's events.
- **snapshot.json:** all current business tables and their full history for this
  shop, with IDs to join related rows. This includes activity from dates outside
  the daily CSV period.
- **manifest.json:** schema version, shop, scheduled and generation timestamps,
  timezone, local date boundaries, table row counts and scope notes. It uploads
  last; the UI marks a run successful only after every upload returns successfully.

At **10 PM on November 4**, the activity CSVs cover November 4's available records
at generation time. They cannot include transactions recorded later that night.
Use a time after shop closing for a full trading day's report. The feature does
not offer a separate previous-calendar-day mode. If set to every seven days,
daily activity CSVs cover only the scheduled day; the snapshot still includes
all seven days and earlier history. Reports reflect the current state of jobs
and reference records, not their state at a historical cutoff.

PIN hashes, device authentication hashes, setup codes, OAuth credentials, login
accounts and login sessions are excluded. Shop name/code/ID are in the snapshot;
logo image bytes are not included. These operational exports are not a database
restore format or a BIR-certified report. CSV text is escaped against spreadsheet
formula execution; unmodified values are available in JSON. Customer contact
information and business history are included, so choose a destination whose
sharing settings you trust.

## Troubleshooting and limits

- **No queued work gets processed:** the recurring job must be installed and use
  the same database, token key, OAuth credentials and environment as the web app.
  The command prints the completed count; per-run errors appear on the owner page.
- **Google `redirect_uri_mismatch`:** match the configured callback exactly,
  including protocol, hostname, port and trailing slash.
- **Picker does not open:** check that Picker API is enabled, the API key's
  referrer restrictions allow this origin, and the project number/client/key all
  belong to the same Cloud project. Creating a folder works without Picker setup.
  Shared drives are not supported by this first implementation; use My Drive.
- **Access expires after about seven days:** external OAuth apps in Testing that
  request Drive scope generally receive refresh tokens with a seven-day lifetime.
  Reconnect for development; configure the appropriate production consent status
  for ongoing use and follow Google's current publication requirements.
- **Repeated API failure:** reconnect Drive if consent was revoked, and check the
  selected parent folder is writable and not deleted/trashed. Provider failures
  are deliberately summarized without persisting credentials or raw API responses.
- **Restricted hosting network:** allow outbound HTTPS to `oauth2.googleapis.com`
  and `www.googleapis.com` for token exchange, account lookup and Drive uploads.
  The browser needs Google sign-in and Picker resources, including
  `accounts.google.com`, `apis.google.com`, `docs.google.com`, `drive.google.com`,
  and their Google static assets. This development environment currently lacks
  Google API egress and real credentials, so automated tests mock Google; an actual
  consent/upload test must run in an environment with that access.
- **Large shops:** report generation currently assembles the snapshot and CSVs in
  memory. This version targets the current app's shop sizes. Measure production
  data size and worker memory/runtime before large deployments. There is no file
  retention/deletion policy; files stay in the user's Drive until they remove them.

## Automated verification

```bash
uv run pytest tests/test_drive_exports.py -q
uv run pytest -q
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
```

Tests cover OAuth state/PKCE and failed consent, encrypted credentials, owner-only
access/CSRF, folder validation, shop isolation, local-day boundaries, formula-safe
CSV output, retry identity, overlapping-worker leases, manual runs while paused,
disconnection, and Drive multipart uploads. Google network calls are mocked.
