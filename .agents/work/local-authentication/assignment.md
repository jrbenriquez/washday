# Local authentication implementation

User request (4 November 2026): implement the discussed authentication flows for local testing, using environment variables for Google OAuth. This is a bounded implementation request; it does not invoke all remaining outcome work.

Scope: verified/allow-listed Google owner sign-in, 14-day owner sessions, minimal owner staff/device/hours/PIN-policy provisioning, persistent enrolled devices, one-use/15-minute setup codes, server-side attempt lockouts, personal shifts ending at closing and landing on Jobs in both modes, request-scoped shared-device PIN approval for payments/claims/manual overrides and optional policies, revocation/reset/deactivation, actor/device event attribution, and reproducible local setup.

The prior people/settings outcomes remain partially implemented until their full criteria, including Undo and broader owner administration, are assessed. Do not reset their budgets or claim whole-group completion. Original acceptance documents remain intact; docs/authentication.md records the accepted authentication amendment. Earlier feature evidence must be regressed on the integrated application.

Acceptance labels for this slice: AUTH-01 Google env/config/callback allow-list; AUTH-02 minimal owner provisioning/isolation; AUTH-03 enrolment/expiry/single-use/hash/cookie; AUTH-04 personal shift/closing/Jobs; AUTH-05 shared per-action PIN/payment/paper; AUTH-06 revocation/deactivation/lockout; AUTH-07 local docs and integrated/browser regression. A real Google consent round-trip and physical Home Screen behavior require local credentials/devices and cannot be substituted by test fixtures.
