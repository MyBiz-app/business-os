# Data safety and privacy labels

Derived from what the three apps and the API store today. Re-check it with each release that adds
a permission or a service. The business is the controller of its clients' data and MyBiz is the
processor (see `docs/reviews/privacy-2026-10.md`).

## What the apps collect

| Data | Why | Linked to the person | Optional |
|---|---|---|---|
| Email, name, phone | Account, bookings, receipts | Yes | Phone: yes |
| Booking, plan, payment and receipt history | The service itself | Yes | No |
| Health declaration (only if the business asks for one) | Safety before a class | Yes | Business's choice |
| Messages with the business and the AI assistant | The service itself | Yes | Yes |
| Push token | Reminders and roster updates | Yes | Yes (permission is asked) |
| Device language and light/dark choice | Display only, stored on the phone | No | n/a |

Not collected: location, contacts, photos, camera, microphone, advertising id, browsing history.
No tracking and no ads. Sign-in and session tokens are kept in the phone's secure store.

## Google Play: Data safety form

- Data collected: Personal info (name, email, phone); Financial info (payment history only: card
  numbers go to the payment provider, never to us); Health info (only when a business uses
  declarations); Messages; App activity (bookings); Device or other ids (push token).
- Purpose: App functionality and account management. Not for advertising or analytics sale.
- Shared with third parties: no sale. Processors act on our behalf: Supabase (auth, database,
  storage), the API host, email, WhatsApp, payments and AI providers where a business turns them on.
- Encrypted in transit: yes. Deletion: yes, by the business's erasure tool and by closing a
  business (deleted 90 days later, X20).
- Account deletion URL: required by Play; see the open item in [`README.md`](README.md).

## Apple: App Privacy labels

Data linked to the user, used for App Functionality only: Contact Info (name, email, phone),
Health & Fitness (declarations), Financial Info (payment history), User Content (messages),
Identifiers (user id, push token), Purchases. "Data used to track you": none.

## Permissions the apps ask for

Only notifications (`expo-notifications`), asked in context. No other native permission is declared.
