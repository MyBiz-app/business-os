# Supabase Auth settings: checklist per environment

`supabase/config.toml` is the source of truth for the **local** stack only. A hosted project
(staging, later production) keeps its own settings in the Supabase dashboard, and they drift:
on 2026-10-10 staging sent an 8-digit sign-in code while `config.toml` said `otp_length = 6`.
Walk this list for every new hosted project and after any change to the auth section of
`config.toml` (Dashboard → Authentication). Only the project owner can change these.

| Setting (dashboard) | `config.toml` | Value to set |
|---|---|---|
| URL Configuration → Site URL | `site_url` | the web app's public address |
| URL Configuration → Redirect URLs | `additional_redirect_urls` | `<web address>/**` and `mybiz://**` |
| Sign In / Providers → Email → confirm email | `[auth.email] enable_confirmations` | on |
| Email OTP length | `[auth.email] otp_length` | 6 (the sign-in screens ask for exactly 6 digits) |
| Email OTP expiry | `[auth.email] otp_expiry` | 3600 |
| Minimum password length | `minimum_password_length` | 6 (raise together with the sign-up form) |
| Anonymous sign-ins | `enable_anonymous_sign_ins` | off |
| Refresh token rotation | `enable_refresh_token_rotation` | on, reuse interval 10 |
| JWT expiry | `jwt_expiry` | 3600 |
| Email templates (Confirm signup, Magic link, Reset password) | `[auth.email.template.*]` | paste the files in `supabase/templates/`; subjects as in `config.toml` |
| Providers → Google | — | on, with the project's own OAuth client; Apple stays off until `AUTH_APPLE_ENABLED` |
| Leaked password protection | — | on (Pro plan only) |
| SMTP | — | the project's own sender before real customers (the built-in one is rate limited) |

After changing anything, run a sign-in with an emailed code on that environment and confirm the
code length and the template language. Moving to `supabase config push` from CI is the longer
fix (launch-readiness P0-8) and needs the project's access token as a secret.
