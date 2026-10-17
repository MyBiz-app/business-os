# Email sending domain (GL22)

Emails (login codes, notifications, announcements) must reach the inbox, not spam. The code is
built and **off**: until the steps below are done, the API keeps its current sender. Needs the
owner's task A6 (a domain and a Resend account). Cost: about $15 a year for the domain; Resend
is free up to 3,000 emails a month.

Below, `example.com` stands for the final domain and `mail.example.com` for the sending
sub-domain (sending from a sub-domain keeps the main domain's reputation safe).

## 1. Resend

1. Create a Resend account, then Domains, Add Domain, `mail.example.com`.
2. Resend shows the DNS records for the domain. Add **all of them** at the registrar's DNS:
   - **SPF**: a `TXT` record on `send.mail.example.com` (value shown by Resend, starts with `v=spf1`) and the `MX` record Resend lists next to it.
   - **DKIM**: a `TXT` record `resend._domainkey.mail.example.com` (the long `p=...` key Resend shows).
   - **DMARC**: a `TXT` record `_dmarc.example.com` with `v=DMARC1; p=none; rua=mailto:dmarc@example.com`.
3. Wait for Resend to show the domain as **Verified** (minutes to a few hours).
4. After two weeks of clean reports, change DMARC to `p=quarantine`, later `p=reject` if the reports stay clean.
5. API Keys, create a key limited to "Sending access" for this domain.

## 2. The API (Render environment)

| Variable | Value |
|---|---|
| `API_EMAIL_PROVIDER` | `resend` |
| `API_EMAIL_API_KEY` | the Resend key |
| `API_EMAIL_FROM` | `MyBiz <no-reply@mail.example.com>` |
| `API_EMAIL_WEBHOOK_SECRET` | the webhook signing secret (step 3) |

A business's own name is shown as the sender's display name and its address as `Reply-To`; the
technical sender is always the verified domain, so SPF and DKIM line up.

## 3. Bounces and complaints (webhook)

1. Resend, Webhooks, Add Webhook: URL `https://<api address>/webhooks/email/resend`, events
   `email.bounced` and `email.complained`.
2. Copy the **Signing Secret** (`whsec_...`) into `API_EMAIL_WEBHOOK_SECRET` and redeploy the API.
   Until it is set the endpoint answers 404.

A hard bounce or a spam complaint puts the address in `email_suppressions`. Every send checks it
first and silently skips the address; the CRM client card shows "email address not reachable".
Soft bounces are ignored (the provider retries them).

## 4. Supabase Auth through the same domain

Dashboard, Project Settings, Authentication, SMTP Settings, enable custom SMTP:

| Field | Value |
|---|---|
| Host | `smtp.resend.com` |
| Port | `465` |
| Username | `resend` |
| Password | the Resend API key |
| Sender email | `no-reply@mail.example.com` |
| Sender name | MyBiz |

Then raise the email rate limit (Authentication, Rate Limits) from the default.

## 5. Check

Send a test email (sign in with an emailed code) to an address from <https://www.mail-tester.com>
and open its report: aim for 10/10. Check SPF, DKIM and DMARC all show "pass". Done when the score is 10/10.
