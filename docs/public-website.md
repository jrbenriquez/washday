# WashDay public website

The `marketing` Django app serves a video-first homepage and a contact flow on
`washdayph.com`. Its URL configuration is separate from the operational app at
`app.washdayph.com`. Both use the existing cloud web service and database.

## Local preview

Keep normal app development unchanged with `MARKETING_PREVIEW` unset. To preview
the public website on localhost with an isolated database:

```sh
uv sync --locked
SQLITE_PATH=/tmp/washday-marketing-preview.sqlite3 uv run python manage.py migrate
MARKETING_PREVIEW=1 SQLITE_PATH=/tmp/washday-marketing-preview.sqlite3 uv run python manage.py runserver
```

Open `http://localhost:8000/`. The preview flag is effective only in DEBUG.
It routes localhost/127.0.0.1/::1 to marketing pages; other app paths on these
preview hosts return 404. Stop the preview and unset the flag to develop the app.
The production marketing host list defaults to `washdayph.com,www.washdayph.com`
and can be changed with the comma-separated `MARKETING_HOSTS` variable.

## Visitor and operator flow

- Homepage → **Book a free demo** → `/contact/?type=demo`.
- Homepage → question link → `/contact/?type=custom`.
- The type remains switchable on the contact page, using native radio controls.
- Both types require name/email. Demo requests require a shop name and may
  include branch count and availability. Custom inquiries require a message.
- Server validation retains submitted values, adds field errors and an error
  summary. JavaScript enhances focus and hides irrelevant fields; it is not
  required to submit a form.
- A valid POST creates an `Inquiry` and redirects to `/contact/thanks/`.
  Availability is free-text preference, not a confirmed booking. The confirmation
  says a team member will agree on a time. No email or calendar request is sent.
- Signed two-hour submission tokens and a unique database constraint make retries
  idempotent. A hidden honeypot rejects simple automated submissions. Django CSRF
  remains enabled. Configure additional rate limiting at the trusted ingress
  before promoting the public form broadly; these controls are not a bot challenge.
- Public requests bypass shop/device lookup under an empty tenant/device context.
  Prospects are platform-level records and do not need an enrolled device or shop.
- Operators use **Marketing → Inquiries** at
  `https://app.washdayph.com/washday-admin/`. Grant staff users `view_inquiry`
  and `change_inquiry` deliberately. Ordinary shop owner access grants neither.
  Operators can filter/search, update follow-up status and internal notes.
  Submitted details are read-only; admin creation/deletion is disabled.

## Domains and deployment

1. Apply the new migration as part of the normal release. The current container
   startup already runs migrations and the image build collects static files.
2. Attach the apex and optional www domain to the existing Openship `web` service,
   port 8000, and enable HTTPS. Set their web DNS records to the correct ingress
   after checking existing records; preserve mail records and the app subdomain.
3. Extend these existing project variables without removing other required hosts:

   ```dotenv
   DJANGO_ALLOWED_HOSTS=app.washdayph.com,washdayph.com,www.washdayph.com
   DJANGO_CSRF_TRUSTED_ORIGINS=https://app.washdayph.com,https://washdayph.com,https://www.washdayph.com
   ```

4. Apply environment changes/redeploy. Keep the owner Google callback at
   `https://app.washdayph.com/accounts/google/login/callback/`. Existing device,
   owner and sync URLs continue to use the app host. Cookies remain host-only.
5. Check both HTTPS hosts, the video, both contact types, admin permissions,
   app login and health checks after deployment.

The public host has only marketing routes and health; app/admin/sync routes
return 404 there. `www.washdayph.com` GET/HEAD requests permanently redirect to
the apex with path/query preserved. Hubs do not serve marketing pages. Local
health checks keep their existing behavior when the preview flag is unset.

## Video and assets

The commercial is committed at `static/marketing/washday-commercial.mp4`
(1920×1080, 30 fps, 30 seconds, ~2.4 MB). It plays only on user request with native
controls and English WebVTT captions. Poster photography is generated; UI/data
in the video are illustrative. Brand fonts and the washer icon come from the
existing repo. No external fonts, analytics, stock asset requests or frontend
build dependencies are added.

To move the MP4 to storage later, set `MARKETING_VIDEO_URL` to the complete HTTPS
MP4 URL and redeploy. Serve it with the correct content type and byte-range
support. The local poster and caption file remain in use.

## Design and verification

The brief borrows the direct product explanation, early demonstration and clear
next steps of [37signals](https://37signals.com/) and
[Basecamp](https://basecamp.com/), with original WashDay copy and styling.
There are no invented testimonials, customer counts or pricing promises.

Run `uv run pytest tests/test_marketing.py --ds=config.test_settings -q` for
forms, storage, token/CSRF validation, admin permissions and host boundaries.
Run the full suite because the change touches shared middleware.
`scripts/check_marketing.py` exercises the local preview with Chromium and writes
screenshots and a recording. It submits fictional contacts only to the local
preview database described above. Install Playwright's FFmpeg helper for recording
or use the installed system FFmpeg at its expected local cache path.
See [browser evidence](ui-audit/marketing/README.md).
