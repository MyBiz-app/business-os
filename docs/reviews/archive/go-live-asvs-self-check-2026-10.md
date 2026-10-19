# OWASP ASVS level 1 self-check (go-live rehearsal, October 2026)

Slice GL24. A self-check, not a penetration test: each line is a level 1 requirement (grouped by
ASVS chapter, wording shortened) with ✅ met, 🟡 met in part or needs a person, 🔴 not met, and
where the evidence is. A professional test is still recommended after 20-50 businesses or before a
large customer (see the go-live scorecard). Evidence names a file or an automated test so a
reader can re-check; "framework" means the framework's default behaviour, with no code of ours.

Result: **79 ✅, 5 🟡, 0 🔴** of 84 lines. The 🟡 lines each name the step that closes them.
Found and fixed during this check: JSON answers carried no cache header (line 8.1); the API now
sends `Cache-Control: no-store` unless a route sets its own.

## V1 Architecture and design

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 1.1 | Components and trust boundaries are documented | ✅ | `docs/spec/archive/v2` architecture chapter; the API decides access (CLAUDE.md principle 1) |
| 1.2 | Access control is enforced on a trusted server layer | ✅ | `app/api/deps.py`, `app/core/permissions.py`; clients hold no authority |
| 1.3 | Business data is separated between businesses | ✅ | Row security on every table; `tests/test_tenant_matrix.py`, `test_database_security.py` |
| 1.4 | Sensitive actions are re-validated on the server | ✅ | Pending Actions are re-checked on confirmation (principle 1) |
| 1.5 | Secrets are kept out of source | ✅ | gitleaks in CI (`ci.yml` security job, nightly `security-nightly.yml`) |
| 1.6 | Third-party providers sit behind swappable interfaces | ✅ | `docs/guides/integrations.md`, `app/providers/` |

## V2 Authentication

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 2.1 | Passwords are at least 10 characters | ✅ | `supabase/config.toml` `minimum_password_length = 10`, applied to staging by `auth-settings-staging.yml` |
| 2.2 | Passwords need letters and digits | ✅ | `password_requirements = "letters_digits"` |
| 2.3 | Changing a password needs a recent sign-in | ✅ | `secure_password_change = true` |
| 2.4 | Passwords are never stored or logged by us | ✅ | Sign-in is Supabase Auth; the API only verifies tokens (`app/core/auth.py`) |
| 2.5 | Sign-in tokens are verified: signature, expiry, audience, subject | ✅ | `app/core/auth.py`; only ES256/RS256 accepted |
| 2.6 | A second factor exists for privileged users | ✅ | Two-step sign-in required for MyBiz staff and owners (`app/core/mfa.py`, `tests/test_mfa.py`) |
| 2.7 | Weak or leaked passwords are refused | 🟡 | The leaked-password check needs Supabase Pro (paid); switch on at go-live ([auth-settings.md](../../deploy/auth-settings.md)) |
| 2.8 | Brute force is limited | ✅ | Supabase sign-in limits per address; API limits by IP and per business (`app/core/rate_limit.py`, `tests/test_rate_limit.py`) |
| 2.9 | Recovery links are single use and expire | ✅ | Supabase Auth defaults; mail configuration in `docs/deploy/email-domain.md` |
| 2.10 | Service credentials are not shared with users | ✅ | Background jobs and the API use separate secrets (`docs/deploy/production.md`) |

## V3 Session management

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 3.1 | Sessions end on sign-out | ✅ | Sign-out clears the session in web and app |
| 3.2 | Sessions end after inactivity | ✅ | Idle sign-out (`apps/web/src/lib/mfa.ts`, `packages/app-kit/src/lib/session-rules.ts` and its test) |
| 3.3 | Tokens are short lived and rotate on refresh | ✅ | One hour access token, rotating refresh token (Supabase settings) |
| 3.4 | Session cookies are protected | ✅ | Set by the Supabase server client in `apps/web/src/lib/supabase/proxy.ts` (HttpOnly, Secure over HTTPS, SameSite) |
| 3.5 | Tokens are not placed in URLs | ✅ | Bearer header only; signed file links carry a separate short lived signature (`app/core/signed_links.py`) |
| 3.6 | A user can end every session | 🟡 | "Sign out of all devices" is on the web (Account, Account security, `scope: global`); the app has no button yet. Not required for level 1; listed as a later improvement |

## V4 Access control

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 4.1 | Every endpoint checks the caller's permission | ✅ | Permission dependencies in `app/api/*`; `tests/test_critical_paths.py`, `test_tenant_isolation.py` |
| 4.2 | Users cannot reach another business's data by changing an id | ✅ | `X-Tenant-Id` is checked against membership in the database; matrix test |
| 4.3 | Staff see only their branches | ✅ | Branch checks on client sub-resources (GL2, #387) |
| 4.4 | Clients see only their own records | ✅ | Client routes filter by the signed-in person; tests in `test_client_profile.py`, `test_dependents.py` |
| 4.5 | Platform (console) access is separate and graded | ✅ | Four MyBiz staff levels; support access is time limited, read-only and audited |
| 4.6 | Administrative actions are logged | ✅ | Audit log screen and `app/core/audit.py` (GL7, #392; `tests/test_audit_log.py`) |
| 4.7 | CORS allows only listed origins | ✅ | `cors_origins` list; production refuses an empty or wildcard list (`app/core/config.py`) |
| 4.8 | Test and payment shortcuts are off in production | ✅ | `simulate-payment` 404 and test cards refused (GL3, #388; `tests/test_production_guards.py`) |

## V5 Validation, sanitization and encoding

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 5.1 | Input is validated by type and length on the server | ✅ | Pydantic models on every endpoint |
| 5.2 | SQL uses bind parameters only | ✅ | `tests/test_sql_fstrings.py`, `test_sql_identifiers.py`; ruff `S` rules |
| 5.3 | Output is escaped for HTML | ✅ | React escapes; emails and PDFs escape (`app/messaging/email_layout.py`, `app/api/pdf.py`); the few `dangerouslySetInnerHTML` uses carry fixed content |
| 5.4 | A Content-Security-Policy limits scripts | ✅ | Per-request nonce policy (`apps/web/src/proxy.ts`, `src/lib/csp.ts`, `csp.test.ts`; GL5, #385) |
| 5.5 | Redirects and URLs from users are checked | ✅ | Return addresses are checked against known paths in the sign-in flow; the API makes no request to a user supplied URL (outgoing calls use fixed https addresses: `messaging/email.py`, `push.py`, `providers/storage.py`) |
| 5.6 | CSV and file imports are bounded and parsed safely | ✅ | `app/catalog/importing.py` (size cap, dialect sniff only on text) |
| 5.7 | Untrusted text given to the AI is marked as data | ✅ | Structural wrapping of untrusted content (GL3, #388); every write is a Pending Action |
| 5.8 | PDF and email templates do not run user code | ✅ | WeasyPrint with escaped text; no template evaluation of user input |

## V6 Stored cryptography

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 6.1 | Sensitive fields are encrypted at rest | ✅ | National id and provider secrets use Fernet (`app/core/identity.py`) |
| 6.2 | Encryption keys can be rotated | ✅ | `MultiFernet` list, `rotate-secrets` job (GL6, #389; `tests/test_key_rotation.py`) |
| 6.3 | No development key works outside development | ✅ | The API refuses to start in production without real keys (`tests/test_production_guards.py`) |
| 6.4 | Random values come from a secure source | ✅ | `secrets`/`os.urandom` for links and codes; Bandit-style `S` rules in ruff |
| 6.5 | Backups are encrypted | ✅ | `age` encrypted dumps (`scripts/backup/backup-db.sh`); rehearsed below |

## V7 Error handling and logging

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 7.1 | Errors do not show stack traces or internals | ✅ | FastAPI returns a generic 500; details only in logs |
| 7.2 | Logs are structured and carry a request id | ✅ | `app/core/logging.py` |
| 7.3 | Logs do not contain secrets or personal data | ✅ | Slow-query log carries no values; log review in `docs/reviews/archive/privacy-2026-10.md` |
| 7.4 | Security events are recorded | ✅ | Audit log, support access, export and deletion |
| 7.5 | Failures reach a person | 🟡 | Alerts to the owner's phone are built (GL13, #400) but need the Sentry and UptimeRobot accounts; steps in [monitoring.md](../../guides/monitoring.md) |

## V8 Data protection

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 8.1 | Sensitive data is not cached by the browser | ✅ | API answers send `Cache-Control: no-store` by default; downloads send `private, no-store` (`app/main.py`, `tests/test_database_security.py`) |
| 8.2 | Personal data can be exported and deleted | ✅ | Per client and per business (GL8, #390) |
| 8.3 | Retention periods are enforced | ✅ | Retention jobs (`app/core/retention.py`) |
| 8.4 | Consent and agreement versions are stored | ✅ | Legal document versions and consent record (GL10, #394; GL9, #391) |
| 8.5 | Personal data is minimised in third-party calls | ✅ | `docs/legal/data-inventory.md`, `vendor-review.md` |
| 8.6 | A data inventory and a procedure exist | ✅ | `docs/legal/` (GL23, #407), drafts for a lawyer |

## V9 Communication

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 9.1 | TLS everywhere | ✅ | Vercel, Render and Supabase terminate TLS; the Docker image serves plain HTTP behind the host's proxy |
| 9.2 | HSTS on the website | ✅ | `apps/web/src/proxy.ts`; `includeSubDomains` switched on with the real domain (checklist) |
| 9.3 | Database connections use TLS | ✅ | Supabase pooler connection strings require it |
| 9.4 | Security headers on API and site | ✅ | nosniff, frame deny, referrer, permissions (`app/main.py`, `apps/web`) |

## V10 Malicious code

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 10.1 | Dependencies are scanned | ✅ | pip-audit and pnpm audit in CI, Dependabot weekly |
| 10.2 | The image is scanned | ✅ | Trivy in the CI security job |
| 10.3 | No secrets in history | ✅ | gitleaks on history, nightly |
| 10.4 | Static analysis runs | ✅ | ruff `S`, ESLint rules, `tests/test_sql_fstrings.py` |
| 10.5 | Uploaded files cannot run as code | ✅ | Type allowlist by bytes, no HTML or SVG, served as attachment with nosniff (GL3) |
| 10.6 | Uploads are scanned for viruses | 🟡 | ClamAV is built and off (about $7 a month); see "Switching on virus scanning" in the checklist |

## V11 Business logic

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 11.1 | Limits stop one business from using everything | ✅ | Per-business request ceiling (GL18, #405), AI credit caps, storage and message quotas (GL21, #406) |
| 11.2 | Multi-step flows cannot be skipped | ✅ | Booking and checkout re-validate on the server; `tests/test_critical_paths.py` |
| 11.3 | Money uses integer minor units | ✅ | Principle 4; invoice and VAT tests (GL20, #408) |
| 11.4 | Double submission is safe | ✅ | Idempotent jobs with run locks (GL14, #398) |
| 11.5 | Public forms are rate limited | ✅ | 20 a minute per IP on public forms (`tests/test_rate_limit.py`) |

## V12 Files and resources

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 12.1 | File size is capped | ✅ | 10 MB (`tests/test_files.py`) |
| 12.2 | File type is checked by content | ✅ | Magic bytes (GL3) |
| 12.3 | Files are not served from the web root | ✅ | Private storage bucket and signed ten minute links (`tests/test_storage.py`) |
| 12.4 | Download names cannot traverse paths | ✅ | Objects are keyed by generated ids |

## V13 API

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 13.1 | The API schema is generated and kept in step | ✅ | CI step "generated API client is up to date" |
| 13.2 | Only expected HTTP methods are accepted | ✅ | Framework routing |
| 13.3 | Webhooks verify a signature | ✅ | Payment and email webhooks require signatures (S1 in security review; email webhook in GL22, #409) |
| 13.4 | Mass assignment is prevented | ✅ | Request models list the allowed fields |

## V14 Configuration

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 14.1 | The production build is hardened and fails closed | ✅ | Startup refuses missing keys, URLs and CORS in production |
| 14.2 | Staging is not indexed | ✅ | `X-Robots-Tag` and robots rules outside production (GL5) |
| 14.3 | Production is reproducible from code | ✅ | `render.production.yaml`, `docs/deploy/production.md` (GL12, #396) |
| 14.4 | Releases can be undone | ✅ | Rollback workflow and expand-then-contract migrations (GL16, #399) |
| 14.5 | Accounts of the team are protected | 🟡 | Two-step sign-in on Supabase, Render, Vercel and GitHub is the owner's step (listed in the checklist and `on-call.md`) |
| 14.6 | Debug features are off | ✅ | `API_ENVIRONMENT` gating; test cards and simulate-payment blocked |
| 14.7 | Unused services and ports are closed | ✅ | The container exposes only the API port |
