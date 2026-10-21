# Data inventory (records of processing)

Draft for a lawyer. One row per kind of personal data MyBiz holds, grouped by whose it is. Table
names are the database tables (`app.*`), so an engineer can verify each row. "Basis" is our reading
of the legal ground and is **to confirm**. "Retention" is what the code does today (the
`purge-expired` job in `apps/api/app/jobs/` and `app/core/retention.py`); where the law sets a
minimum, that is written as "legal minimum, to confirm".

Every business-owned table carries `tenant_id` and Postgres row level security, so a business only
reads its own rows. MyBiz's own tables have no API access at all (see
`apps/api/tests/test_database_security.py`).

Roles: **C** = MyBiz is the controller, **P** = MyBiz is the processor for the business that owns
the data.

## A. Business owners and staff (MyBiz is the controller)

| Data | Tables | Typical fields | Purpose | Basis | Retention | Role |
|---|---|---|---|---|---|---|
| Account and sign-in | `users`, Supabase Auth, `login_devices` | name, email, phone, language, avatar, device label, last seen | Run the account, secure sign-in | Contract | While the account exists; sign-in removal in the app deletes it | C |
| Membership and roles | `tenant_members`, `tenant_roles`, `invitations` | role, branches, permissions, invite email | Access control | Contract | While a member; deleted with the member | C |
| Billing of the business | `billing_accounts`, `platform_invoices`, `checkouts` | plan, invoice lines, VAT, payment status (no card numbers) | Charge for the service | Contract, tax law | Legal minimum, to confirm (invoices are never deleted with the business) | C |
| Support | `contact_requests`, `support_grants` | name, email, message, support access window | Answer requests | Legitimate interest, contract | Requests 12 months; grants until ended or expired | C |
| Consent and acceptance | `consent_events`, `legal_acceptances` | which document and version, when, how | Prove consent and acceptance | Legal duty, legitimate interest | Kept as proof (no deletion today), to confirm | C |
| MyBiz team | `platform_staff`, `platform_audit` | email, level, permissions, actions taken | Run the console, audit | Legitimate interest | Audit kept; to confirm | C |
| Incident banners | `platform_incidents` | public text, who opened and resolved | Tell users about outages | Legitimate interest | Kept (no personal data except the team member's email) | C |

## B. Staff of a business (the business is the controller, MyBiz is P)

| Data | Tables | Typical fields | Purpose | Basis | Retention | Role |
|---|---|---|---|---|---|---|
| Work schedule and attendance | `shifts`, `shift_templates`, `shift_swaps`, `shift_changes`, `staff_hours`, `staff_availability`, `staff_time_off`, `time_off_requests`, `time_clock_entries`, `time_clock_rules`, `time_clock_approvals` | times, branches, requests, clock in/out | Schedule and pay | Contract | While employed; then the business's rules | P |
| Employment and payroll | `employment_profiles`, `form101_forms`, `pay_components`, `pay_adjustments`, `payroll_runs`, `payroll_run_lines`, `payslip_corrections` | wage terms, tax form 101 fields, bank account, payslips | Payroll | Contract, tax and labour law | Legal minimum, to confirm (payslips and tax forms) | P |
| National ID numbers | `person_identities` | encrypted ID number, hash for duplicates, country | Payroll and legal forms | Legal duty | Deleted with the person; encrypted with `API_SECRETS_KEY` | P |
| Staff accounts | as in A | | | | | C and P |

## C. Clients of a business (the business is the controller, MyBiz is P)

| Data | Tables | Typical fields | Purpose | Basis | Retention | Role |
|---|---|---|---|---|---|---|
| Client card | `clients`, `client_notes`, `client_locations`, `client_addresses`, `dependents` | name, email, phone, birth date, notes, addresses, children or pets | Run the service | Contract, consent | Until the client or business erases; erased clients are cleared ("Deleted client") | P |
| Bookings and plans | `bookings`, `sessions`, `session_series`, `appointments`, `entitlements`, `entitlement_freezes`, `class_invites` | what, when, which plan | Deliver the service | Contract | Kept as history; upcoming bookings cancelled on erasure | P |
| Payments and receipts | `payments`, `receipts`, `quotes`, `quote_lines`, `issued_documents`, `retainers`, `time_entries` | amounts, last four card digits and card type (no card numbers), accepted-by name | Accounting | Contract, tax law | Legal minimum, to confirm; the name on them is replaced on erasure | P |
| Health declarations | `health_declarations` | answers to the business's health questions | Safety of training | Consent (sensitive data), to confirm | Deleted on erasure | P |
| Documents and files | `client_documents`, `business_files`, `file_folders` and the storage provider | uploaded files, signatures | Hold agreements and records | Contract, consent | Per folder rule; deleted with the client or business | P |
| Reviews | `reviews` | rating, comment | Quality | Consent | Rating kept in averages; comment deleted on erasure | P |
| Leads | `leads`, `lead_activities` | name, contact, source, notes | Sales | Legitimate interest, consent | 12 months without activity if not a client | P |
| Messages | `messages`, `notifications`, `message_templates`, `campaigns`, `whatsapp_inbox`, `whatsapp_conversations`, `whatsapp_offers` | message text, delivery state, phone | Communicate | Contract, consent for marketing | Messages 24 months; WhatsApp inbox and chats 12 months | P |
| Marketing consent | `consent_events`, columns `marketing_consent_at` | consent, withdrawal, source | Spam law proof | Legal duty | Kept as proof | P |
| Social | `client_social`, `client_friendships` | friend codes, who is friends | Optional social features | Consent | Deleted on erasure | P |
| Data exports | `data_exports` | link to an export file | Answer access requests | Legal duty | Expires, then purged | P |

## D. AI assistants

| Data | Tables | Typical fields | Purpose | Basis | Retention | Role |
|---|---|---|---|---|---|---|
| Conversations and tasks | `ai_conversations`, `ai_agents`, `ai_scheduled_tasks`, `ai_task_runs`, `pending_actions` | text the owner or client typed, tool calls, results | Assistant features | Contract, consent | 12 months | P |
| Usage and limits | `usage_events`, `ai_credit_limits`, `ai_credit_alerts`, `tenant_ai_settings` | counts and spend, no content | Billing, limits | Contract | Kept | C |

The text goes to the AI provider (Anthropic). The backend decides what the assistant may do; the
assistant has no direct database access.

## E. Logs and operations

| Data | Tables | Typical fields | Purpose | Basis | Retention | Role |
|---|---|---|---|---|---|---|
| Audit log | `audit_log` | who did what, when, on which record | Accountability, security | Legal duty, legitimate interest | 24 months | P (business log), C (MyBiz log) |
| Push tokens | `push_tokens` | device token | Notifications | Consent | Until the device is removed or the user signs out | C |
| Application logs | Render and Vercel logs (not the database) | request ids, status codes, no bodies | Operate and secure | Legitimate interest | Provider default (days); to confirm | C |
| Error reports | Sentry (when switched on) | stack traces, request ids | Fix errors | Legitimate interest | Provider default; no personal data sent on purpose | C |
| Backups | Supabase backups; encrypted second copy at Cloudflare R2 when switched on | everything above | Recovery | Legitimate interest, security duty | 30 days | C and P |

## F. A business that leaves

A business that closes is read-only, then deleted 90 days after it leaves (`CLOSED_BUSINESS_GRACE_DAYS`),
except the invoices MyBiz must keep (go-live GL8). The owner can export all the business's data
before that. Individual clients can ask the business for export and erasure (`app/api/privacy.py`),
and a person can delete their own sign-in from the app.

## Open points for the lawyer

- The tier of the data security regulations (see the [README](README.md)).
- Whether health declarations, ID numbers and bank details need extra safeguards or registration.
- The legal minimum retention of invoices, payslips and tax forms, and who keeps them (business or
  MyBiz) after a business is deleted.
- Application log and backup retention at the providers, in days.
