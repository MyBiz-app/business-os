# Privacy review before go-live (October 2026)

Part of [#51](https://github.com/MyBiz-app/business-os/issues/51), with Israel's Privacy
Protection Law (Amendment 13) in mind. Each business is the controller of its clients' data;
MyBiz processes it for them. This review checks that a business can answer a client's request
to see or erase their data, for everything the product now stores.

## What we hold about a business's client

| Data | Where | Export | Erase |
|---|---|---|---|
| Name, email, phone, birth date, notes, custom fields | `clients` | ✅ | Cleared ("Deleted client") |
| Bookings, plans, freezes | `bookings`, `entitlements`, `entitlement_freezes` | ✅ | Kept (history); freeze reasons cleared; upcoming bookings cancelled |
| Payments and receipts | `payments`, `receipts` | ✅ | Kept for accounting; the name on receipts replaced |
| Health declarations | `health_declarations` | ✅ | Deleted |
| Visit notes, notifications, messages | `client_notes`, `notifications`, `messages` | ✅ | Deleted |
| Ratings and comments | `reviews` | ✅ | Rating kept in averages; comment deleted |
| The lead that became the client | `leads`, `lead_activities` | ✅ | Deleted |
| **Addresses** (on-site jobs, #42) | `client_addresses`, copy on `sessions.address` | ✅ new | **Deleted, copies cleared** (new) |
| **Pets and children** (#43) | `dependents` | ✅ new | **Deleted**; visits stay without who came (new) |
| **Documents and signatures** (#45) | `client_documents` + storage provider | ✅ new (list) | **Deleted, files too** (new) |
| **Quotes and bills** (#44, #45) | `quotes`, `quote_lines` | ✅ new | Kept for accounting; the name typed to accept replaced (new) |
| **Time logged for the client** (#45) | `time_entries`, `retainers` | ✅ new | Kept (the business's billing records) |
| Client app sign-in | Supabase Auth user, linked by `clients.user_id` | | Unlinked from the business |

Before this review, export and erasure predated addresses, pets and children, documents,
quotes and time; they now cover them (`app/api/privacy.py`, migration 0055, tested in
`test_privacy.py`).

## Checked and sound

- Both requests are owner-only (`clients.privacy`) and written to the business's audit log.
- An erased client gets nothing new: no bookings, messages or plans (`ensure_not_erased`).
- Personal data never leaves the business: RLS on every table, and MyBiz staff see a business
  only when its owner lets them in (read-only, audited) or when acting for it (audited).
- Provider secrets are encrypted; sign-in tokens are verified (see the security review).

## Decisions and work before go-live

1. **Retention periods** (owner's decision): how long to keep leads that never became clients,
   website contact requests, messages and the AI assistant's conversations, and a closed
   business's data after it leaves. Nothing is deleted automatically today.
2. **The AI assistant's conversations** may name clients; they are not in the client export or
   erasure yet. With the real AI provider (#50) they also leave our servers: the provider's
   data terms belong in the privacy notice.
3. **Privacy notice and processing agreement** for businesses (MyBiz as processor), and the
   list of sub-processors (Supabase, the host, email, WhatsApp, payments, invoicing, AI).
4. **Database registration and a data-security officer** if the law's thresholds apply to
   MyBiz once it has customers: a legal check, not code.
