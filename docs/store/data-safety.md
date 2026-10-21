# Data safety and privacy labels

Derived from what the three apps and the API store today. Re-check it with each release that adds
a permission or a service. The business is the controller of its clients' data and MyBiz is the
processor (see `docs/reviews/archive/privacy-2026-10.md`).

## What the apps collect

| Data | Why | Linked to the person | Optional |
|---|---|---|---|
| Email, name, phone | Account, bookings, receipts | Yes | Phone: yes |
| Profile picture (taken with the camera or picked from photos) | Shown on the profile and to the business | Yes | Yes |
| Booking, plan, payment and receipt history | The service itself | Yes | No |
| Health declaration (only if the business asks for one) | Safety before a class | Yes | Business's choice |
| Messages with the business and the AI assistant | The service itself | Yes | Yes |
| Staff only: national ID number (encrypted, hidden by default, every view logged), bank account, tax form (Form 101) answers | Payroll and legal employer duties, entered by the employee or the business | Yes | Business's choice |
| Staff only: shifts, availability, clock-in and clock-out times (no location), payslips and yearly summaries | Scheduling, attendance and payroll | Yes | No for staff of a business that uses them |
| Push token | Reminders and roster updates | Yes | Yes (permission is asked) |
| Device language and light/dark choice | Display only, stored on the phone | No | n/a |

Not collected: location (the time clock does not read GPS), contacts, microphone, advertising id,
browsing history. The camera and photos are used only when the person picks a profile picture.
Face ID / fingerprint unlock happens on the phone: no biometric data leaves it and the app never
sees it. No tracking and no ads. Sign-in and session tokens are kept in the phone's secure store.
Crash reports (Sentry) carry no names, messages or ID numbers; see `docs/guides/monitoring.md`.

## Google Play: Data safety form

- Data collected: Personal info (name, email, phone, government ID number for staff); Financial
  info (payment history and, for staff, bank account for payroll; card numbers go to the payment
  provider, never to us); Health info (only when a business uses declarations); Messages; Photos
  (profile picture only); App activity (bookings, staff attendance); App info and performance
  (crash logs); Device or other ids (push token).
- Purpose: App functionality and account management. Not for advertising or analytics sale.
- Shared with third parties: no sale. Processors act on our behalf: Supabase (auth, database,
  storage), the API host, email, WhatsApp, payments and AI providers where a business turns them on.
- Data handling: all data is encrypted in transit; the ID number, bank account and Form 101
  answers are also encrypted at rest with a key held outside the database.
- Encrypted in transit: yes. Deletion: yes, by the business's erasure tool and by closing a
  business (deleted 90 days later, X20).
- Account deletion: in the apps, Me, "Delete my account" (`DELETE /me`). Play also wants a web
  address for it: use `/legal/privacy` (it explains the steps and the contact) until a dedicated
  page exists (open item in [`README.md`](README.md)).

## Apple: App Privacy labels

Data linked to the user, used for App Functionality only: Contact Info (name, email, phone),
Health & Fitness (declarations), Financial Info (payment history, staff bank account), User
Content (messages, profile photo), Sensitive Info (staff national ID number), Identifiers (user
id, push token), Purchases, Diagnostics (crash data, not linked to identity). "Data used to track
you": none. Export compliance: the app only uses standard encryption (HTTPS), so
`ITSAppUsesNonExemptEncryption` is `false` in `app.json` and the export question is skipped.

## Permissions the apps ask for

| Permission | Why | Asked | Text shown (`app.json`) |
|---|---|---|---|
| Notifications | Reminders, roster updates | In context, after sign-in | Operating system dialog |
| Camera | Take a profile picture | Only when the person chooses "take a photo" | "Allow MyBiz to use the camera to take your profile picture." |
| Photos | Pick a profile picture | Only when the person chooses "pick a photo" | "Allow MyBiz to use your photos for your profile picture." |
| Face ID | Unlock the app | Only if the person turns on app lock | "Allow MyBiz to use Face ID to unlock the app." |

Not declared, and kept off on purpose: microphone (`RECORD_AUDIO` is blocked in `app.json`, the
image picker is set not to ask for it), location, contacts, calendar, tracking
(`NSUserTrackingUsageDescription`). `apps/client-app/test/store-config.test.mjs` fails if one of
them appears.

## Sign-in rules

The app signs in with email or phone and a one-time code. There is no "Sign in with Google" in the
app, so Apple's rule 4.8 (offer Apple sign-in next to other third-party logins) does not apply.
**If a Google or Facebook button is ever added to the app, "Sign in with Apple" must be added in
the same release**, or the iOS review will reject it. The website's optional Google/Apple buttons
are not part of the app.
