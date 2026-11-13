# Public website browser evidence

Captured in Chromium against a local isolated SQLite database, using fictional
contacts only. No production records, emails, DNS changes or deployment actions.

## Screenshots

- [Homepage, desktop](home-desktop.png) — 1440×1000, video and primary CTA visible.
- [Full homepage](home-full.png) — complete benefit-led page.
- [Contact, desktop](contact-desktop.png) — demo selection and optional availability.
- [Homepage, mobile](home-mobile.png) — 390×900, video first in reading order.
- [Contact, mobile](contact-mobile.png) — responsive native form.
- [Validation errors](contact-errors.png) — focused summary and inline errors.
- [Custom inquiry](custom-inquiry.png) — demo-only inputs hidden.
- [Demo confirmation](demo-success.png) — request saved, time still to be agreed.
- [Inquiry confirmation](custom-success.png) — saved inquiry.

## Recording

[Contact flow, MP4](contact-flow.mp4) is a 1280×900 screen recording showing the
homepage CTA, an invalid demo submit, correction and successful demo request,
return to the homepage, custom inquiry and successful confirmation. The recording
is silent; the homepage commercial retains its own music when played.

The preview database was inspected after recording: one `demo` and one `custom`
record were present, both with `status=new`. The demo retained branch count and
availability; the custom inquiry did not retain demo-only fields.

## Verification

- Video plays when requested and has native controls and English captions.
- No autoplay; public pages require no account, device or tenant.
- Home and both contact modes fit at 320, 390, 768, 1024 and 1440px.
- Error summary receives focus. Values remain after failed submission.
- Native type selection/server validation work without JavaScript.
- Both inquiry types save and redirect to confirmation. No browser JS errors.
- Django tests cover CSRF, expired/forged tokens, idempotent retries, invalid input,
  operator permissions, host routing and the hub boundary. Full suite passes.
- Django check, migration drift check and collectstatic pass.

See [browser.json](browser.json) and reproduce with
`uv run python scripts/check_marketing.py` while the isolated marketing preview
is running. The script submits test inquiries locally. Chromium is required;
Playwright video recording needs its FFmpeg helper or the system FFmpeg at the
expected helper path. This environment used `/usr/bin/chromium` and system FFmpeg.

Live TLS/DNS, ingress rate limiting, external Google consent and production
PostgreSQL deployment were not exercised. Deployment steps are in
[public-website.md](../../public-website.md).
