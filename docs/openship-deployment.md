# Deploying the cloud app with Openship

The root `openship.json` selects `docker-compose.yml`. It builds the existing
Django image, runs database migrations before Gunicorn, and serves the web
service on container port **8000**. The image defaults to `DJANGO_DEBUG=0` and
runs as the non-root `washday` user. Static assets are collected and compressed
during the image build.

This is the cloud deployment. Branch hubs continue to use `compose.hub.yml`.
Production cloud storage requires PostgreSQL; local SQLite databases are not
copied into the image or migrated automatically.

## Before importing

1. Choose the app hostname and create its DNS A record using the server profile
   stored outside this repository. Do not change existing apex or `www` records.
2. Add a dedicated PostgreSQL service from the Openship catalog. Use its internal
   hostname, database, role, and password; keep the database unexposed. This must
   be the application's own database, separate from Openship's control-plane
   database. Arrange database backups and a tested restore before real use.
3. Configure a Google OAuth **Web application** client. Add
   `https://<app-host>/accounts/google/login/callback/` as an authorized redirect
   URI. The existing allauth flow requires both the client ID and client secret.
   Enter credentials directly into Openship; do not commit them.

## Import and configure

Import this GitHub repository from the branch containing these changes. Keep
the compose file set to `docker-compose.yml`; select the `web` service rather
than a second service inferred from the CSS tooling's `package.json`.

Set these **Openship project variables**, replacing angle-bracketed instructions
with the actual values. Do not paste these placeholders as real credentials.

| Variable | Value |
| --- | --- |
| `DJANGO_SECRET_KEY` | A new random secret, at least 50 characters |
| `DJANGO_ALLOWED_HOSTS` | `<app-host>` without scheme or path |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://<app-host>` |
| `PGDATABASE` | Dedicated application database name |
| `PGHOST` | Catalog database's internal hostname |
| `PGUSER` | Application database role |
| `PGPASSWORD` | Application database password |
| `GOOGLE_CLIENT_ID` | Google Web application client ID |
| `GOOGLE_CLIENT_SECRET` | Google Web application client secret |

The compose file already supplies `DJANGO_DEBUG=0`, `APP_ROLE=cloud`,
`PGPORT=5432`, and `MEDIA_ROOT=/data/media`. Only override `PGPORT` if the
database connection details require it. Never enable the development scope or
browser-enrolment bypasses in production. Missing Django secret, explicit host
configuration, or PostgreSQL connection settings prevent startup. Missing Google
credentials leave owner sign-in disabled; they must be configured before use.

If PostgreSQL belongs to a separate Openship project, create an **internal
project connection** from it to Washday. This establishes the shared Docker
network. Copy the generated connection's hostname into `PGHOST`; a short service
name from the database project's own network may not resolve from Washday.
Openship can inject `DATABASE_URL`, but Washday currently uses the separate
`PG*` variables instead.

On macOS, generate and copy a Django secret without printing it:

```sh
openssl rand -base64 48 | tr -d '\n=' | pbcopy
```

Configure the service's **container port to 8000** and mark it **exposed**. Attach
the hostname as a **project domain** targeting `web`, and enable HTTPS. The
container has no published host port: only the trusted Openship edge should
reach it. The edge must overwrite `X-Forwarded-Proto` with the real request
scheme, which Django trusts to enforce HTTPS and issue secure cookies.

Deploy after configuring the variables and database. Startup migrations are
idempotent, but back up before every schema-changing upgrade. This small
deployment uses one web service with two Gunicorn workers; do not run concurrent
schema-changing deployments.

Startup waits for PostgreSQL connectivity before running migrations. Openship's
compose deployment can start the container before attaching its linked database
network, so immediate migration attempts can fail DNS resolution. The readiness
command retries connection failures for a 60-second window, with a five-second
PostgreSQL connection timeout per attempt, then fails startup if the database is
still unavailable. Migrations themselves run once and retain normal failure
behavior. SQLite hubs skip this network-readiness check.

To reproduce and check this startup ordering locally with disposable containers:

```sh
docker build -t washday-runtime .
python3 scripts/check_database_startup.py --image washday-runtime
```

The check starts the app without its database network, attaches it after twelve
seconds, and requires successful migrations and HTTP 200 without a container
restart or traceback. It deletes only its own temporary local test resources.

## Persistence and verification

The named `washday-media` volume persists `/data`, including uploaded shop logos
under `/data/media`. Back up this volume separately from PostgreSQL. Redeploys
retain it; removing the volume loses uploads.

The `/health/` endpoint is unauthenticated and queries the migrations table.
It returns HTTP 503 when the database cannot be queried. The compose probe sends
`X-Forwarded-Proto: https`, so the HTTPS redirect does not break the local probe.

In the deployed service's terminal, run:

```sh
python manage.py check --deploy
python manage.py showmigrations --plan
```

HSTS starts at one hour and applies only to this hostname. Django's deployment
check will warn that HSTS subdomains and preload are not enabled (`security.W005`
and `security.W021`). Review the hostname's scope before enabling either;
preload requires a separate browser-list submission and a longer HSTS policy.
All other warnings need investigation before production use.

Check HTTPS `/health/`, `/owner/login/`, and a collected `/static/` asset through
the actual domain. Confirm that signed-out users cannot access owner pages and
that Google sign-in returns to the HTTPS callback without CSRF errors. Verify
logo upload persistence after a redeploy.

An environment change requires **Apply environment changes** or a redeploy;
Restart keeps the old environment. Port/exposure changes require a service
redeploy. Confirm the running container was recreated after these changes.

## First shop and rollout

Django admin is available on the cloud service at `/washday-admin/` for staff
accounts with the appropriate Django permissions. Inside the deployed container,
create the initial superuser with `/app/.venv/bin/python manage.py createsuperuser`
after migrations have run. The image collects admin static assets during the
build; startup migrations also install the admin log tables. Admin provides
built-in user/group management, requires no enrolled device, and is unavailable
on branch hubs. Approved Google shop owners do not automatically receive admin
access.

Migrations create an empty database. They do not create a shop, business data,
owner, or staff, and do not import the developer's local dataset. Production
shop provisioning and a deliberate data migration are separate steps. Do not
run `seed_demo`, which is development-only. Once the real shop exists, use the
existing command to allow the owner's verified Google email:

```sh
python manage.py allow_owner <owner-google-email> --shop-code <existing-shop-code>
```

Real Google consent, TLS issuance, database/media backups, shop provisioning,
physical device enrolment, and the direct pilot must be verified on the chosen
deployment. Passing local container checks does not complete those rollout gates.
