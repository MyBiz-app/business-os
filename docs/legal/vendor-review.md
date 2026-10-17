# Annual review of the sub-processors

Draft process for a lawyer to approve. Do it once a year, before adding a provider, and after any
news of a breach at one of them. Record the result in the table at the bottom and keep the
evidence (links, dates) in the incident or review note.

The public list is the "Sub-processors" page of the site (`marketing.legal.subprocessors` in
`packages/i18n/messages`). Change that page **before** a provider is added or replaced; businesses
may object under the data processing agreement.

## Checklist per provider

1. Still needed? Is there a cheaper or safer choice (all outside services are behind swappable
   providers, see [integrations](../integrations.md))?
2. Which data does it receive, and is that the least needed?
3. Where is the data stored (country and region)? If outside Israel, is the transfer covered
   (adequacy, contract terms)? **To confirm with counsel.**
4. Security: a current certification or report (for example SOC 2, ISO 27001), encryption at rest
   and in transit, two-step sign-in on our account, who on our side has access.
5. Contract: a data processing agreement signed or accepted online, a breach notice duty on their
   side (how fast), deletion at the end.
6. Incidents in the last year at the provider, and how they answered.
7. Access review: remove people and API keys no longer needed; rotate keys per
   [key rotation](../runbooks/key-rotation.md).
8. Cost and limits still fit the plan.

## Current list (October 2026)

| Provider | Used for | Data | State |
|---|---|---|---|
| Supabase | Database, sign-in, file storage | All business data | In use |
| Render | API and background jobs | Data in transit and in memory | In use |
| Vercel | Website and web app | Pages, session cookies; no database | In use |
| Anthropic | AI assistants | Text the assistants work on | In use when a business uses AI |
| Expo | Push notifications | Device tokens, notification text | In use |
| Resend | Email delivery | Recipient, subject, body | Planned (needs the domain) |
| Meta (WhatsApp Business) | WhatsApp messages | Phone numbers, messages | Adapter disabled until connected |
| Payments and invoicing provider | Charging and tax invoices | Payment tokens, invoice data | Adapter disabled until chosen |
| Sentry | Error reports | Stack traces, request ids | Optional |
| Cloudflare R2 | Encrypted second backup | Encrypted dumps | Off until the owner switches it on |
| GitHub | Code and CI (no customer data) | Source code, CI secrets | In use |

## Review log

| Date | Reviewer | Providers reviewed | Findings and actions |
|---|---|---|---|
| | | | |
