# Authentication flows

Accepted for local implementation on 4 November 2026, following the user's authentication design request and instruction to implement it with environment-based Google OAuth.

- Google-only owner sign-in using a verified, allow-listed email, a shop-bound session and a 14-day session lifetime. No public signup/password login.
- Owner provisions branch staff and shared/personal devices. Staff PINs are four digits, hashed and unique among active staff in a branch.
- An installation QR/link identifies an invitation; it is never a device credential. A separate six-digit code expires after 15 minutes and is single-use. Home-screen setup is the normal UI; an explicit DEBUG-only browser setup option supports local testing.
- Enrolment stores an opaque HttpOnly device cookie and only its digest on the server. Keys/code/PIN values are never stored in Events.
- Personal devices require a name/PIN sign-in, automatically expire 24 hours after sign-in, and open Jobs in both simple/full modes. This accepted default supersedes the older full-mode Machines landing page.
- Shared devices have no staff session. Default PIN actions are payment, claim and manual override. Paid intake, self-service and paper collection obey payment rules. Each protected request validates a PIN; it does not cache a general unlock.
- Revocation, staff deactivation and PIN reset invalidate subsequent relevant requests on this server. An offline hub can only apply a cloud change once received; replication remains later work.
- Authentication is this implementation slice. Full owner settings/reporting, Undo and hub deployment are not certified by it.
