# Support

How a business or a client reaches us, and how we answer. The support address and the status page
are **placeholders until the owner picks them** (go-live item: a real support address and status page).

## Channels

| Channel | For | Notes |
|---|---|---|
| In-app support inbox | Business owners and staff | Messages reach the MyBiz console support inbox ("Working inside a business" lets support see what the customer sees, with a banner and an audit entry) |
| Support email | Anyone | `support@<domain>` (to be created with the domain). Forwarded to the owner until there is a team |
| Status page | Everyone during an incident | To be chosen (a free hosted status page is enough). Link it from the site footer |

Languages: Hebrew first, English. Reply in the language of the message.

## Response targets (while there is one person)

| Priority | Example | First reply | Fix target |
|---|---|---|---|
| Urgent | Nobody can sign in; data looks wrong or exposed; payments or bookings failing for many | Same day, also outside work hours | Start immediately, see [on-call](on-call.md) |
| Normal | A business cannot do one task; wrong notification | Next working day | Within the week |
| Low | Question, wish, wording | 3 working days | Backlog |

## Working inside a customer's business

1. Ask the customer in writing before entering their business (the support banner and audit entry
   record every visit; do not browse for curiosity).
2. Use the support role, not an owner password. Never ask a customer for their password or their
   sign-in code.
3. Leave the business when done (the banner has a Leave button).

## Common requests

| Request | Answer |
|---|---|
| "I can't sign in" | Check the email spelling; the code is 6 digits and expires; resend; check spam. If email is down, see [on-call](on-call.md) |
| "Delete my account / my data" | Owners close the account from settings; the business is deleted after 90 days. A client's export and erasure are in the client profile |
| "Export my data" | Client export from the profile; business export is a support task until built |
| "Wrong time shown" | Check the business time zone in settings; times are stored in UTC |
| "A booking disappeared" | Check the audit log first; if data loss is suspected, treat as urgent and see the [restore runbook](restore-runbook.md) |

## Privacy rules for support

- Share only what the verified owner of that business is entitled to. Verify by replying to the
  email on file.
- Never paste personal data into public issues, logs or chats. Use ids.
- A suspected data exposure is urgent and has legal clocks (GDPR 72 hours to the regulator, Israel's
  privacy authority rules): follow the incident section in [on-call](on-call.md).
