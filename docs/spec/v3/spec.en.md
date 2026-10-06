# MyBiz — Product Specification (v3)

Version 3 · October 2026 · Working document. The decision log (docs/DECISIONS.md) records every decision in detail; this document describes the product as a whole.

## 1. What MyBiz is

MyBiz is an operating system for small and medium service businesses: fitness and training, beauty and spa, clinics and health, classes and lessons, automotive services and more, each on equal footing. One platform runs the business day to day — schedule and appointments, clients, plans and payments, leads, messages, reports and an AI assistant — and gives every business its own branded app for its clients.

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

### 3.4 Owners, businesses and branches

A MyBiz customer is a person, and a person can own several businesses. For example, Adir owns a chain of pizzerias with four branches and, separately, a barbershop in Tel Aviv with one branch: two businesses, five branches.

- **Business**: has its own industry, name, brand, team, clients, plan and monthly invoice. Data never mixes between businesses; even the same person's two businesses are separate.
- **Branch**: a place where the business works, with its own address and rooms. A business starts with one branch; each additional branch is the "extra branch" item on the invoice, which follows the number of active branches.
- **My businesses**: one page shows every business the person belongs to, with its industry, branches and the key numbers of today and this month; from there they open a business or add a new one. A switcher in the side menu moves between businesses from any page.
- **Current branch**: inside a business with several branches, a selector in the header chooses "all branches" or one branch. The schedule, the dashboard's numbers, reports, sales and the client list follow it, and new sessions, sales and clients are filed under it.
- **What belongs to a branch**: sessions and appointments (where they happen), sales (where they were sold), clients (their home branch, optional) and team members (the branches they work at; none means all). Services, plans and prices belong to the whole business.
- **Roles**: a person's role is per business (owner of one, manager in another). Within a business, a team member assigned to branches sees those branches first; limiting permissions per branch comes later.

## 4. Industries: categories and sub-categories

The fitness studio was the prototype. Every industry now stands on equal footing: no industry is "the main one", and the core never asks which industry a business belongs to. Industries are organized in two levels:

- **Category**: a family of businesses that work the same way, for example "Beauty & Spa". It defines the shared defaults: what clients are called, how they book (group classes, one-to-one appointments or both), cancellation policy, whether a plan is needed to book, a health declaration, the client details the business keeps, and the starter services and plans.
- **Sub-category**: a specific kind of business inside the family, for example "Barbershop" or "Nail studio". It inherits everything from its category and overrides only what differs, usually its name, its starter services and sometimes an extra client detail. A sub-category can have sub-categories of its own when needed.

A business picks its sub-category (or only the category) when it signs up. The choice sets its starting point, and everything stays editable afterwards.

### 4.1 The five main categories

Chosen because the current core already serves them fully (schedule, appointments, plans, client app) and together they cover most service businesses in Israel.

| Category | Sub-categories | Clients are | Booking | Typical client details |
|---|---|---|---|---|
| Fitness & Training | gym, pilates studio, yoga studio, CrossFit box, functional training, personal trainer | members | group classes, personal sessions; memberships and punch cards | goal, injuries; health declaration |
| Beauty & Spa | hair salon, barbershop, cosmetics and facials, nails, laser hair removal, spa and massage | clients | appointments | hair type, color formula, skin type, allergies |
| Clinics & Health | physiotherapy and rehabilitation, dental clinic, nutrition, aesthetic clinic, therapy and coaching | patients | appointments, treatment series | ID number, health fund, referred by, allergies |
| Classes & Lessons | dance, martial arts, music lessons, private tutoring, kids' activities | students | weekly classes and private lessons; term and monthly plans | level, parent's contact (for children) |
| Automotive | garage, detailing and car wash, tires | customers | appointments | plate, make, model, year, mileage, next inspection |
| Sports & facilities (beta) | padel and tennis clubs, football pitches, rehearsal studios, meeting rooms and coworking | players | courts and rooms by the hour (paid in the app or at the venue) | level, preferences; instrument (studios); company (meeting rooms) |

Several industries in the original list live inside these as sub-categories: wellness and spa (Beauty & Spa); rehabilitation, nutrition, therapy and coaching (Clinics & Health); education, dance, music and kids' activities (Classes & Lessons).

### 4.2 The category template

Every category and sub-category is one entry in a shared catalog that the API, the website and the apps all read, so adding one never means changing code across the system. An entry holds:

| Part | What it sets |
|---|---|
| Identity | key, parent (for a sub-category), icon and color, status (live, beta, planned) |
| Words | what clients are called and every industry word in the interface, in Hebrew and English |
| Booking | booking modes, cancellation window, plan required to book, health declaration |
| Starter content | services (name, duration, price per currency, color) and plans (membership or punch card) |
| Client details | extra fields the business keeps (text, number, date, choice) |
| Modules | the recommended starting set of modules |
| Marketing | name, short line, three benefits and the industry page text, in both languages |

To open a new category or sub-category: run the generator (`pnpm vertical:new <key> --parent <category>`), fill in the entry and its texts, and the checks confirm it is complete (both languages, valid prices, a known parent and module set). It then appears on the marketing site, in the sign-up journey, in onboarding, in the contact form and in the apps by itself. A category marked "planned" shows on the site as "coming soon" with a "tell me when" option, before it is open for sign-up.

### 4.3 Future categories (catalog)

These need one new capability in the core first. Each capability is built once for the core and then serves every category that needs it.

| Category | Examples | New capability it needs |
|---|---|---|
| Home & field services | cleaning, air conditioning, electricians, plumbers, pest control | On-site jobs: the client's address, travel time, assigning a technician, quotes. **Built (#42): Home & field services is open as beta**; quotes come with #44 |
| Pet services | dog grooming, training, boarding, dog day care | Dependents: several profiles under one client (pets; also children for Kids & Youth). **Built (#43): Pet services is open as beta** (grooming, training, day care); Kids & Youth keeps a profile per child |
| Kids & Youth (full) | enrichment centers, camps, toddler gyms | Dependents and parent accounts |
| Creative & events | photographers and studios, DJs, event suppliers, small venues | Quotes, deposits and event projects |
| Professional services | consultants, accountants, lawyers, agencies | Documents and retainers, time-based billing |

Until a category opens, interested businesses can leave their details through the contact form, which records the industry.

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

- Sales: a month of receipts, totals by payment method, CSV export for the accountant.
- My profile: everyone sets the name the team, clients and reports see.
- Locked modules: modules the business doesn't have stay in the menu with a lock and open a preview — what it does, a picture, what changes on the invoice — with one-click "add to plan".
- Getting started: a first-steps checklist on the dashboard for a new business.

Phase 2 review: every screen checked on phone and computer, Hebrew/light and English/dark, for accessibility, errors and layout (automated crawl plus a visual pass).

## 8. The MyBiz console

Built: businesses list, business detail, AI usage, contact requests, billing revenue, audited support access granted by owners.

Built in phase 3:
- Its own menu — overview, businesses, inbox, billing, team, audit — where each item appears only for someone who may open it.
- The MyBiz team: a primary owner nobody can remove, change or disable (even through direct database access), owners (partners), managers (who handle employees with the permissions they hold themselves) and employees. People are added by email before they ever sign in, and access can be paused instead of removed.
- Permissions: see businesses, work inside businesses, billing, inbox, usage, manage employees. Every level gives only what it holds, and only owners handle owners and managers.
- Working inside a business: staff who may do it enter any business and work there like a manager, to handle a complaint or fix a mistake — never privacy requests. Every request appears in the business's own log, which its owner reads, with changes marked. Others still need the owner's read-only support grant.
- Actions for the owner: extend the trial, change the plan, credit an invoice — each written to both logs.
- Inbox: requests from the website and messages businesses send from Settings, with status (new, in progress, done), someone handling them and internal notes.
- Audit log (owners only): everything the MyBiz team did.

## 9. Apps

- Client app (built, Expo; also runs in the browser): join, home, schedule and appointments, bookings and plans, buying with promo codes, receipts, ratings, updates, profile, health declaration.
- Business app (built in phase 4, extended to run the whole day from the phone): Today — a day strip for the week ahead, each day's classes and appointments, and what needs attention (plans ending, clients drifting away, leads to call back, health declarations); a session — check-in and no-show, booking a client in (or onto the waiting list), cancelling a booking and a visit note; Clients — search, filters (with or without a plan, not seen in 14 days), adding a client, and a client card with contact, plans and selling one (simulated payment), what's coming up, recent visits, notes and a WhatsApp message; Leads — by stage, a lead card with call, moving the stage, logging a call, turning them into a client, and a new lead; Messages — what was sent to clients and leads; Numbers — the key figures of the last 30 days; Me — profile, language, theme, branch and switching between businesses. Each person sees only what their permissions and the business's modules allow.
- MyBiz staff app (built in phase 4, extended in its second round): Home — the platform's numbers (open requests, new businesses this week, businesses, active clients), this month's billing, and the open requests and new businesses themselves; Businesses — search, sort and a business card (owner, numbers, modules, invoices, and more trial days for billing staff); Inbox — open and handled requests, and a request card (call, WhatsApp, email, status, taking it, internal notes, opening its business); Me. Each staff member sees only what their level and permissions allow.
- All three apps share one kit (sign-in, theme, language, right-to-left, accessible components), so a fix in one place reaches all of them.
- Still to do: final polish of the client app and builds for the app stores (at go-live).

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
| 1 — Marketing website | Complete site and the sign-up journey with cart, summary, payment, welcome email, guide | Done |
| 2 — Business web app | Locked modules with previews and upsell; full review and polish; sales; profiles | Done |
| 3 — MyBiz console | Team levels and permissions, full visibility and actions, support inbox | Done |
| 4 — Apps | Business app and MyBiz staff app built, shared app kit; remaining: client app polish and store builds | Mostly done |
| 5 — Industries | The category template (category → sub-category) in one shared catalog; the five main categories with their sub-categories | Done |
| 6 — Businesses and branches | One owner with several businesses, each with several branches: my businesses, a current branch, data and numbers per branch, a full demo | In progress |
| 7 — More categories | Core capabilities for the future categories (resources, on-site jobs, dependents, quotes and deposits), each opening its categories. Done: resources (courts and rooms by the hour), which opened Sports & facilities | In progress |
| Go-live | Real payment, invoicing, email, WhatsApp, AI key, domain, production hardening | When the owner decides |

The live status of the work — done, in progress and next — is kept in `docs/STATUS.md` and in the repository's GitHub issues, updated with every merged change.

Each phase ends with a review: every page and button checked, accessibility and dark mode, tests, and a tidy codebase.
