# MyBiz — Product Specification (v3)

Version 3 · October 2026 · Working document. The decision log (docs/DECISIONS.md) records every decision in detail; this document describes the product as a whole.

## 1. What MyBiz is

MyBiz is an operating system for small and medium service businesses: studios and gyms, hair and beauty salons, clinics, garages and more. One platform runs the business day to day — schedule and appointments, clients, plans and payments, leads, messages, reports and an AI assistant — and gives every business its own branded app for its clients.

- Market: Israel first (Hebrew, right-to-left, shekels), then the US and Europe (English).
- Model: software as a service. A business pays a monthly subscription built from modules; a 14-day free trial first.
- Principle: one vertical-agnostic core. What differs between industries (words, default services, client details, forms) comes from configuration "packs", not separate products.

## 2. The surfaces

MyBiz has three web surfaces and three app experiences. Clients of the businesses never use a website: they only use the app.

| Surface | Who | What |
|---|---|---|
| Marketing website | Business owners who are considering MyBiz | Product, industries, pricing, contact, and the sign-up journey that builds a plan and starts the subscription |
| Business web app (CRM) | The business: owner, managers, front desk, staff | Everything that runs the business |
| MyBiz console | MyBiz itself: owners and staff of MyBiz | Every business, owner and client; support, billing, revenue, team and permissions |
| Client app | Clients of the businesses | Join a business, book, buy plans, pay, rate visits, get updates |
| Business app | Business owners and staff on the go | The day's schedule, clients, check-in, messages, key numbers |
| MyBiz staff app | MyBiz team | Businesses, support requests, alerts |

## 3. Roles and permissions

### 3.1 Inside a business

| Role | Access |
|---|---|
| Owner | Everything, including billing, team and privacy requests. A business can have several owners. |
| Manager | Everything except privacy requests (export / erase a client's data). |
| Front desk | Clients, schedule, bookings, sales, assistant. |
| Staff (instructor, barber, therapist, mechanic) | Sees clients and the schedule, checks clients in, writes visit notes. |
| Custom roles | The owner switches individual permissions on or off; nobody can grant more than they hold. |

### 3.2 Inside MyBiz (the console)

| Level | Access |
|---|---|
| Primary owner | Everything on the platform. Cannot be removed, demoted or locked out by anyone. The first account: adire7399@gmail.com. |
| Owner | Same access as the primary owner (for a partner), except that they cannot remove or change the primary owner. |
| Manager | Manages MyBiz employees and the permissions owners allowed to managers; works on businesses (support, billing) within those permissions. Cannot create owners. |
| Employee | Only the permissions given to them (for example: view businesses, answer contact requests, support access). |

Rules: every level can only give permissions it holds itself; only owners create owners and managers; everything a MyBiz person does inside a business is written to the audit log and visible to that business's owner.

### 3.3 Clients

A client signs in to the client app with an email code, joins businesses with a join code or QR, and only ever sees their own data.

## 4. Industries (vertical packs)

| Pack | Clients are | Booking | Starter content | Extra client details |
|---|---|---|---|---|
| Fitness | members | group classes (+ personal sessions) | memberships, punch cards | goal, injuries; health declaration |
| Beauty | clients | appointments | haircuts, color, beard | hair type, color formula, allergies |
| Clinic | patients | appointments | first visit, treatment, follow-up | ID number, health fund, referred by, allergies |
| Garage | customers | appointments | periodic service, oil change, diagnostics | plate, make, model, year, mileage, next inspection |

Adding an industry means adding a pack: words, default services and plans, client fields, policies.

## 5. Modules and pricing

A subscription is the core plus modules. Prices are placeholders until pricing is finalized.

| Item | What it adds | Monthly (ILS, placeholder) |
|---|---|---|
| Core (required) | Schedule, appointments, clients, plans, sales, receipts, reports, team, closed days, reviews | 99 / 149 / 249 by active clients (up to 100 / 300 / 1,000) |
| Client app | The branded client app: booking, buying, updates | 49 |
| AI Basic / AI Pro | Assistant answers questions; Pro also prepares actions for approval | 49 / 119 |
| CRM and leads | Lead pipeline, inquiry form, follow-ups, conversion | 39 |
| WhatsApp & SMS | Broadcasts, templates, automatic reminders | 29 (+ usage) |
| Extra location | Each location after the first | 29 each |
| Coming soon | Advanced analytics, finance agent, marketing agent | — |

Rules:
- 14-day free trial, then a monthly invoice in arrears, charged to the card on file.
- Modules a business doesn't have still appear in its menu, locked, with a short preview of what they do and a button to add them; adding one updates the next invoice.
- Usage (AI credits, messages, storage) is measured per business.

## 6. The sign-up journey (marketing website)

The goal: a business owner who found MyBiz on Google (phone, tablet or computer) understands the product, gets convinced, and subscribes in a few enjoyable minutes.

1. Landing on the website: home, features, industries, pricing, about, contact, legal pages — Hebrew and English, light and dark, fast on phones.
2. "Start free": a step-by-step builder in the style of booking a low-cost flight:
   1. About the business: industry, name, size (active clients, staff, locations).
   2. The base: the core plan matched to the size, with what's included.
   3. Add-ons, one per screen, each with a clear benefit, a picture of the feature and the price ("Add the client app?", "Want an AI assistant that answers in seconds?", "Turn inquiries into clients with CRM?", "Remind clients on WhatsApp automatically?").
   4. A live cart that follows the user, with the monthly total and what they saved by the trial.
   5. Summary: every line, the total after the trial, the trial end date, terms.
   6. Account: email and password (or continue if signed in).
   7. Payment: card on file for after the trial (simulated until a payment provider is chosen).
   8. Done: the business is created with the chosen modules, and the owner lands in the business web app with a getting-started checklist.
3. Welcome email: sent right after sign-up with the plan, trial dates, the business's join code, links to the web app, the client app and the getting-started guide, and how to get help.
4. Getting-started guide: a public page that explains the first steps (branding, services, hours, team, inviting clients) with links.

## 7. The business web app (CRM)

Built (all in Hebrew and English, light and dark, accessible, phone-friendly):
- Dashboard: today's sessions, KPIs with comparison, weekly charts, trial and billing reminders.
- Schedule: week view, one-off and weekly sessions, series editing, copy week, closed days, appointments (1:1) with staff working hours and time off, walk-in booking.
- Session page: roster, waitlist, check-in, booking for clients.
- Clients: search and filters, profile, industry details, visit notes, plans, bookings, health declaration, ratings, messages, privacy (export / erase), import from CSV / Excel.
- Plans: memberships and punch cards, selling, freezing, receipts; promo codes.
- Leads (CRM module): pipeline board, activity log, conversion, public inquiry form.
- Messages (WhatsApp & SMS module): broadcasts to segments, templates, direct messages, wa.me links, automatic reminders.
- Reports: by service, staff member and hour; clients to reach out to; satisfaction.
- Assistant (AI module): questions in plain words, actions for approval.
- Team: invitations, roles, custom roles, working hours, time off.
- Settings: business details, branding, booking rules, modules, billing (trial, card, invoices), support access.

To complete in phase 2: locked modules in the menu with previews and "add to plan", and a full review of every screen.

## 8. The MyBiz console

Built: businesses list, business detail, AI usage, contact requests, billing revenue, audited support access granted by owners.

To complete in phase 3:
- MyBiz team: primary owner, owners, managers, employees, with permission switches.
- Full visibility: every business, its owners, team and clients.
- Actions on any business (fix data, change modules, extend a trial, credit an invoice), each written to the audit log.
- Support inbox (contact requests and complaints) with status.

## 9. Apps

- Client app (built, Expo; also runs in the browser): join, home, schedule and appointments, bookings and plans, buying with promo codes, receipts, ratings, updates, profile, health declaration.
- Business app (phase 4): the owner's and staff's day on the go.
- MyBiz staff app (phase 4): businesses, support, alerts.

## 10. Simulated services (until go-live)

| Service | Now | At go-live |
|---|---|---|
| Card payments (clients and subscriptions) | Simulated test card, real screens and flows | Israeli payment provider (Cardcom / Grow / PayPlus / Tranzila) |
| Invoices and receipts | Numbered sample documents | Invoicing provider (Morning / iCount / EZcount) |
| AI assistant | Demo mode with scripted answers from real data | Claude API key |
| Email | Gmail SMTP (prototype) | Transactional email provider and a domain |
| WhatsApp / SMS | Logged, not sent; free wa.me links | WhatsApp Business API / SMS gateway |

Swapping a simulated service for a real one changes only its adapter; screens and data stay.

## 11. Architecture and quality

- Web: Next.js (TypeScript), Tailwind. Apps: Expo (React Native). API: FastAPI (Python). Database, sign-in and storage: Supabase (Postgres).
- Tenant isolation: every business row carries its business id and is protected by database row-level security as well as by the API.
- The backend is the authority; the AI acts only through approved tools, and sensitive actions wait for a person's approval.
- Money in minor units with a currency; times stored in UTC and shown in the business's time zone.
- Hebrew and English with right-to-left layout; dark mode; accessibility (WCAG AA, IS 5568) checked automatically.
- Tests: API tests for every feature, end-to-end browser tests for every flow, CI on every change.
- Privacy: Israeli Privacy Protection Law (Amendment 13): export and erase on request, minimal data, audit log.

## 12. Roadmap

| Phase | Content | Status |
|---|---|---|
| Foundation | Core, verticals, schedule, clients, plans, client app, AI, reports, modules, billing, CRM, messaging, reviews, promo codes | Done |
| 1 — Marketing website | Complete site and the sign-up journey with cart, summary, payment, welcome email, guide | In progress |
| 2 — Business web app | Locked modules with previews and upsell; full review and polish | Next |
| 3 — MyBiz console | Team levels and permissions, full visibility and actions, support inbox | Next |
| 4 — Apps | Client app polish, business app, MyBiz staff app | After the websites |
| Go-live | Real payment, invoicing, email, WhatsApp, AI key, domain, production hardening | When the owner decides |

Each phase ends with a review: every page and button checked, accessibility and dark mode, tests, and a tidy codebase.
