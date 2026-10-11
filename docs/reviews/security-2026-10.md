# Security review before go-live (October 2026)

Part of [#51](https://github.com/MyBiz-app/business-os/issues/51). Scope: the API (sign-in,
business isolation, public endpoints, webhooks, file uploads and links, raw SQL, secrets).
The web app and the Expo apps call the API with the user's token and hold no extra authority,
so the API is where access is decided (principle 1).

## Fixed in this review

| # | Finding | Severity | Fix |
|---|---|---|---|
| S1 | A payment webhook completed any checkout whose id it named, whatever business its address named. A business can connect a real payments provider with its own secret, so it could sign a notification with that secret and mark another business's checkout as paid (it would need that checkout's random id). | Medium | `app.complete_provider_checkout` now takes the business from the webhook's address and refuses a checkout of another business (migration 0054). Tested in `test_integrations.py`. |
| S2 | Signed file links fell back to the development key when `API_SECRETS_KEY` was missing, in every environment. That key is public (it is in the repository), so anyone could forge a link to a document whose ids they knew. | Medium | Outside local development and tests, a missing key now fails instead of signing (`app/core/signed_links.py`), like provider secrets already did. Tested in `test_documents_time.py`. Staging and production must set `API_SECRETS_KEY`. |

## Checked and sound

- **Sign-in**: tokens are verified against Supabase's published keys (ES256/RS256 only), with
  audience, expiry and subject required (`app/core/auth.py`).
- **Business isolation**: every request is scoped by `X-Tenant-Id`, and the database decides
  membership (`app.current_tenant_id()` checks `tenant_members`); RLS is on every table and
  checked by `test_database_security.py`. Support access is read-only at the database level and
  audited; MyBiz staff acting in a business are audited for the owner.
- **Public endpoints** (`/public/*`): quote links use about 244 random bits and are served by
  narrow SECURITY DEFINER functions; inquiries and contact forms are rate-limited; file links
  are HMAC-signed and expire in 10 minutes.
- **Uploads**: an allowlist of types (no HTML or SVG), a 10 MB cap, files served as attachments
  or inline with `X-Content-Type-Options: nosniff`; logos are checked by their bytes, not the
  name or header.
- **Raw SQL**: every query passes values as bind parameters; the only interpolated pieces are
  constants or column names taken from Pydantic models (`set_clause`).
- **Secrets**: provider secrets are encrypted at rest (Fernet) and never returned; a missing
  `API_SECRETS_KEY` fails outside development.

## Still to do before go-live

- Monitoring and alerts, and a backup restore drill (need the hosting choices in #34).
- The privacy review (Amendment 13): data inventory, retention, the erasure flow end to end.
- A review of the web app's server actions and the Expo apps' token storage.
