# MyBiz - System Specification (v4)

Version 4 · 19 October 2026 · The source of truth for the product. Written from the full-system spec of 19 October 2026 ([`docs/plans/2026-10/system-spec-full-2026-10-19.md`](../../plans/2026-10/system-spec-full-2026-10-19.md), Hebrew) and from the code on `main`. The decision log ([`docs/DECISIONS.md`](../../DECISIONS.md)) records every decision in detail; the status board ([`docs/STATUS.md`](../../STATUS.md)) records what is built, in progress and missing. "(#123)" is the number of the pull request that built the item.

Earlier specs (v1, v2, v3) are kept in [`docs/spec/archive/`](../archive/).

---

## 1. MyBiz in one sentence, and one picture

**MyBiz is an operating system for small and medium service businesses** (fitness, beauty, clinics, classes, garages, courts, home services, pets, events, professional services, food): schedule and appointments, clients, plans and payments, leads, messages, payroll, reports, a team of AI agents, and a branded app for the business's clients. Israel first (Hebrew, shekels), then the US and Europe.

**The four layers:**

```
Layer 1   MyBiz (the owner and the MyBiz team)
            |  web console + "MyBiz team" area in the app
            |  sees all businesses, billing, support, AI, system health
            v
Layer 2   The business owner and their team  (MyBiz's customer)
            |  marketing site + sign-up -> web CRM + "business" area in the app
            |  manages clients, schedule, money, staff, AI
            v
Layer 3   The business's client  (trainee, patient, car owner...)
            |  "client" area in the app: joins with a code, books, buys, pays
            v
Layer 4   The client's client  (the child or dog a client books for, an invited
                               friend, a visitor filling a form on the business's
                               site, someone who receives a quote link)
```

**Note on layer 4:** "the client's client" is anyone the system serves through the business's client, or with no account at all. The business owner as MyBiz's "customer" and their own client are layers 2 and 3.

**One system, three screens:**

| Screen | Address today | Who uses it |
|---|---|---|
| Website (marketing + CRM + console) | `business-os-alpha-drab.vercel.app` (future domain `mybizapp.click`) | Visitors, businesses, MyBiz team |
| One app (Expo: one codebase for Android, iPhone and browser) with three areas: client, business, MyBiz team | `mybiz-client-app.vercel.app` + Expo Go | Clients, businesses, MyBiz team |
| Server (API: the layer every screen talks to, which enforces all the rules) | Render | Everyone, through the screens |

---

## 2. Layer 1: MyBiz (the owner and the MyBiz team)

### 2.1 Who is on the team and what they may do

| Level | What is allowed |
|---|---|
| **Primary owner** (`adire7399@gmail.com`) | Everything. No one can remove, demote or lock them, not even through the database |
| **Owner** (partner) | Same as the primary owner, except touching the primary owner |
| **Manager** | Manages staff and grants only permissions they hold themselves |
| **Staff** | Only the permissions granted |

**7 permissions:** view businesses, work inside a business, billing, support requests, usage data, team management, messages to businesses. Every team member must use two-factor authentication (2FA: a code from an app in addition to the password). People are added by email before they have signed in. (`apps/api/migrations/versions/0037_platform_staff.py`)

### 2.2 The web console (`/platform`)

| Page | What you see and do |
|---|---|
| Home | Platform numbers, new businesses, open requests, AI spend |
| Businesses + business card | Search and sort; on the card: numbers, usage, credits, modules; extend a trial, change modules, void an invoice |
| Working inside a business | An authorized team member enters a business and works like a manager (handle a complaint, fix a mistake). Every action is logged in the business's log and MyBiz's log, and the owner sees a banner |
| Requests | Requests from the site and from businesses: status, assignee, internal notes |
| Messages to businesses | Written in Hebrew and English, channels, audiences, preview, test, scheduling, results |
| Incident banners | Open and close an "incident / maintenance" banner shown on all sites and the app |
| Site orders (MyBiz Sites) | Board by stage, notes, image download, ready-made prompt for building the site |
| Billing | Revenue by month and currency, debts, grace days, collection settings |
| Churn | Cancellations and pauses, reasons, trend |
| Growth | Sign-up funnel, active businesses, biggest consumers |
| AI | AI cost versus revenue per business, model settings, emergency stop, pause AI for one business, use of the Claude/ChatGPT connector, and a console AI assistant (5 hats) |
| System health | Background jobs, queues, file volume, AI spend, recent crashes |
| Team | Add, edit, suspend and remove MyBiz team |
| Integrations | Default provider for each service (payments, invoicing, messaging...) and how many businesses connected their own |
| Audit log | Everything the MyBiz team did (owners only) |

### 2.3 The "MyBiz team" area in the app

Home (requests, new businesses, numbers, this month's billing), businesses (search and card, including adding trial days), requests (a card with call / WhatsApp / email, status, notes), me.

### 2.4 How MyBiz earns

A monthly subscription from each business, built from a core and modules (section 7.3), after a 14-day trial. Also: the websites service (ILS 790 + ILS 49 a month for a landing page alone, ILS 490 + ILS 29 a month with the system), extra AI users, and paid AI overage. VAT 18%, a monthly invoice with running numbers, collection stages. **The payment processing itself is off until go-live.**

### 2.5 What is planned for this layer

See [`docs/plans/2026-10/plan-agents-console-2026-10-19.md`](../../plans/2026-10/plan-agents-console-2026-10-19.md): a map of 12 console AI agents and 14 console additions.

---

## 3. Layer 2: The business owner and their team

### 3.1 How a business arrives: the marketing site and sign-up

**Site pages:** home, features, AI team (`/ai-team`), about, contact, getting-started guide, industries (a page per industry), pricing (with a calculator), websites (`/websites`), and six legal documents (terms of use, privacy, cancellation, DPA, sub-processors, accessibility; all drafts until a lawyer reviews them). Hebrew and English, light and dark.

**Sign-up (`/start`), in the style of a low-cost flight booking:** track (new business / existing business moving over, or "website only") -> account -> industry -> business details and size -> base package -> add-ons, one per screen (client app, AI, CRM, WhatsApp) -> website -> packages, support and setup -> summary, with a live cart throughout -> payment (simulated) -> the business is created and the owner lands in the CRM with a "first steps" list. A welcome email carries the business's join code.

**An existing business moving over:** a "moving to MyBiz" center: upload files from the previous system, AI-assisted column mapping, a message to clients, or "do it for me".

### 3.2 Structure: person, businesses and branches

- One person can own several businesses (for example a pizza chain with 4 branches, and a hair salon). Data of different businesses never mixes, even for the same person.
- Each business has branches. A selector at the top of the screen: "all branches" or one branch, and all data follows it.
- **Solo mode:** a one-person business gets a small menu and a simple dashboard, without branches and staff.

### 3.3 Roles inside the business

| Role | What is allowed |
|---|---|
| Owner | Everything (including billing, staff, privacy requests, payroll approval, viewing ID numbers) |
| Manager | Everything except privacy requests, ID numbers and payroll approval |
| Branch manager | Only their branches: clients, schedule, sales, reports, AI, staff and attendance, payroll proposal |
| Front desk | Clients, schedule, bookings, sales, AI |
| Staff (instructor, barber, therapist, mechanic) | Sees clients and schedule, marks attendance |
| Custom roles | The owner switches each of the 27 permissions on or off. No one can grant more than they hold |

Two-factor authentication: mandatory for the MyBiz team; optional for owners and managers with a warning and an "I understand the risk" acknowledgement that is written to the audit log (#480); a business can require it of all its staff.

### 3.4 The web CRM: all areas

| Area | What is there |
|---|---|
| **Dashboard** | What is happening today, metrics with comparison and a free date range, every number clickable to its filtered list, trial and billing reminders |
| **Reports** | By service, staff member and hour; clients worth following up; satisfaction; a "without staff" filter |
| **AI team** | A map of 9 agents (main, secretary, marketing, sales, finance, staff, service, analyst, creative), custom agents through a 6-step wizard, an org chart, scheduled tasks, a morning summary, a usage meter, and a floating chat bubble on every screen |
| **Schedule** | Week, one-off and recurring classes, personal appointments by staff hours, closed days, a smart waitlist (3 modes), over-capacity booking for staff only, hourly booking of courts and rooms |
| **Clients** | Search and filter, a client card (details by industry, visit notes, plans, bookings, health declaration, ratings, messages, children / pets), import from CSV and Excel, a join code and QR for the app, export and deletion on a privacy request |
| **Leads** (CRM module) | Stage board, activity log, conversion to client, a public inquiry form |
| **Messages** (WhatsApp module) | Messages to groups, templates, direct message, automatic reminders, AI replies on WhatsApp |
| **Content** (Studio module) | A social media studio with drafts from the creative agent |
| **Catalog** | Services, plans and punch cards, discount codes, on one page with three tabs |
| **Money** | Quotes and events (including a deposit), invoices, receipts, sales and purchases from the app, monthly billing for retainers and hours, branded PDF documents |
| **Hours** | Time tracking for professional service providers |
| **Branches** | List, rooms, and a branch map with "where clients come from" |
| **Files** | System folders (documents, form 101, payslips are saved automatically) and the business's own folders |
| **My website** | Order a website from MyBiz, an 8-step brief wizard, tracking until launch, visits and inquiries |
| **Staff** | People, a full employee card, availability hours, an org chart, a shift board, vacations, shift swaps, a time clock, monthly and annual payroll (net, PDF payslip, bank file, digital form 101), bonuses, custom roles |
| **Settings** | Business details, plans, booking rules and cancellation policy, branding with a live preview, modules, billing and cancelling the MyBiz subscription, integrations (connect your own provider), AI connections (Claude / ChatGPT), audit log, data export and closing the business, help |
| **Locked module** | A module the business does not have appears in the menu with a lock, opens as a preview, and offers "add to plan" |

### 3.5 The "business" area in the app

Tabs: **Today** (day by day for the week, what needs attention), **Clients**, **Inquiries** (leads and messages), **Numbers**, **Me**. Screens: client and lead card, a class (check-in, no-show, booking, cancel), a quote, front-desk court booking, a field technician's workday ("on my way / started / finished"), my shifts, availability, time clock, my documents (payslips), form 101, AI team and chat with an agent (including approval cards), content studio. Each person sees only what their permissions and modules allow.

### 3.6 Connecting Claude and ChatGPT (MCP)

A business owner can connect their own Claude or ChatGPT to MyBiz (MCP: a protocol that lets an AI app use the tools of another system). Secure sign-in (OAuth), read tools always available, and actions only as a "proposal" that waits for approval in the CRM.

---

## 4. Layer 3: The business's client

### 4.1 Sign-in and joining

The client does not use the website, only the app. They sign in with a code by email and join a business with a join code or QR (several businesses are allowed). Marketing consent is off by default. After joining they immediately see the business's cancellation policy.

### 4.2 What the client does

| Tab / screen | What is there |
|---|---|
| **Home** | Cards by industry, a health declaration reminder, documents, a rating request, a book-an-appointment button |
| **Schedule** | Day / week / month, open spots in classes, appointments and courts |
| **Bookings** | My plans, what is coming, history |
| **Updates** | What the business did (cancelled a class, approved a freeze...) |
| **Profile** | Details, language, color theme, account deletion (an Apple requirement) |
| Booking an appointment | Service -> staff member -> day -> time; asks "for whom?" (child / pet) and "which address?" for a home service |
| Court / room | Hourly booking and payment |
| Waitlist | For a service, a whole day or an hour range, up to 5 active requests |
| Plan freeze | A request (with a document), early end, tracking |
| Payment | Card (simulated today: a test card, no money is charged), discount codes |
| Receipts, quotes, documents | View, approve or decline a quote and pay a deposit, sign documents |
| Health declaration | With a typed signature |
| Friends | Friend code, requests, inviting to a class |
| Children / pets, addresses | Manage my profiles and addresses |
| Visit rating | 1-5 stars and a note |

### 4.3 Cancellation policy

Three layers, the most specific wins: plan -> service -> business. Separate cancellation windows for a class, a personal appointment and a court. Defaults by industry. "Return the class to the client" for staff. Free cancellation for 30 minutes after being promoted from the waitlist.

---

## 5. Layer 4: The client's client

| Who | What the system gives them | How |
|---|---|---|
| **A client's child or pet** (dependents) | Their own profile with fields by industry (for example breed, age); appointments and classes are booked for them | The client manages their own, staff manage all (#43) |
| **An invited friend** | An invitation to a class, a limited profile | Found only by code or exact phone / email, inside one business |
| **A visitor on the business's website** | An inquiry form (also embeddable in an existing site) that becomes a lead in the CRM | `/inquiry/[code]`, `/embed/inquiry/[code]` |
| **Someone who received a quote** | View, approve or decline, and pay a deposit, with no account | Private link `/q/[token]` |
| **Someone who scanned a QR** | A branded landing page of the business that leads to joining | `/join/[code]` |
| **A visitor on a site we built for a business** (MyBiz Sites) | The business's site or landing page, with an inquiry form connected to the CRM | Ordered from "My website" |
| **A message recipient** | A branded message, a short "unsubscribe" link | Marketing only with consent |

**What does not exist:** a "guest" who comes to a class with no account and no membership (there is no such entity), and a parent account separate from the client (the parent is the client, the child is a dependent).

---

## 6. AI in the system, across all layers

| Layer | What exists |
|---|---|
| MyBiz | A console assistant with 5 hats and read tools; AI cost versus revenue; an emergency stop. Planned: 12 agents |
| Business | 9 built-in agents + up to 3 / 10 custom, each with data domains, branches and allowed roles; actions only through an approval card; scheduled tasks; a morning summary and weekly suggestions; Claude / ChatGPT connection |
| Client | No direct AI for the client. The business can enable AI replies on WhatsApp |

**Economics:** a credit is one cent of model cost. Basic AI ILS 49 a month = 400 credits (about 400 questions), advanced ILS 119 = 1,200. 3 / 10 AI users are included, an extra user is ILS 19 with 150 credits. Overage ILS 8 per 100 (off by default). A daily pace limit: one person cannot use more than 15% of the quota in a day. Models: Haiku by default, Sonnet for complex questions. **Without an API key the system answers in demo mode.**

**Safety rules:** the server is the authority; the AI sees only what the person may see; every change waits for approval and is validated again on approval; external text is wrapped as data; every action is logged.

---

## 7. What cuts across all layers

### 7.1 Industries (verticals)

One catalog, category -> sub-category, read by the site, sign-up, app and server. Each industry sets the words ("trainees" / "patients"), how booking works, the cancellation policy, client fields, starter services and plans, and recommended modules. 11 categories:

| Category | State | Sub-categories |
|---|---|---|
| Fitness and training | Active | Gym, Pilates, Yoga, CrossFit, Functional, Personal trainer |
| Beauty and spa | Active | Hair salon, Barbershop, Cosmetics, Nails, Laser, Spa |
| Clinics and health | Active | Physiotherapy, Dental, Nutrition, Aesthetics, Therapy |
| Classes and lessons | Active | Dance, Martial arts, Music, Private lessons, Kids' classes |
| Automotive | Active | Garage, Detailing, Tires |
| Sports and venues | Beta | Padel and tennis, Football fields, Rehearsal rooms, Meeting rooms |
| Home services | Beta | Cleaning, Air conditioning, Electricians, Plumbers, Pest control |
| Pets | Beta | Grooming, Training, Day care |
| Events and creative | Beta | Photographers, DJs, Event suppliers, Small halls |
| Professional services | Beta | Consultants, Accountants, Lawyers, Agencies |
| Food | Beta | Pizzeria, Cafe, Restaurant, Bakery, Catering |

Adding an industry: `pnpm vertical:new` and filling in the file ([`docs/guides/verticals.md`](../../guides/verticals.md)).

### 7.2 Messages and channels

In-app notifications for the client, push to staff phones, email (Gmail today; Resend from our own domain at go-live), WhatsApp and SMS (recorded but not sent today; free wa.me links work), marketing messages only with consent and an unsubscribe link.

### 7.3 Modules and prices (all provisional, in code at `apps/api/app/commerce/modules.py`)

| Item | ILS per month |
|---|---|
| Core by active clients | 99 (up to 100) / 149 (up to 300) / 249 (up to 1,000) |
| Client app | 49 |
| Basic / advanced AI | 49 / 119 |
| CRM and leads | 39 |
| WhatsApp and SMS | 29 + usage |
| Finance agent / marketing agent | 69 each |
| Extra branch | 29 |
| More modules | Branded app, CRM automation, advanced analytics, content studio, payroll, AI replies on WhatsApp, volume packs (Plus / Max), priority / VIP support, guided / full setup |

### 7.4 External providers (each behind an "adapter" that can be swapped without changing screens)

| Service | Today | At go-live |
|---|---|---|
| Payments | Simulated | An Israeli provider (#46, the owner's decision) |
| Invoicing | MyBiz receipts | Morning / iCount / EZcount (#47) |
| AI | Anthropic (demo mode without a key); OpenAI and Gemini off | Anthropic with a production key |
| Email | Gmail | Resend + domain |
| WhatsApp / SMS | Simulated | WhatsApp Business / an SMS provider |
| Files | The database | Supabase Storage |
| Virus scanning | Off | ClamAV |
| Second backup | Off | Cloudflare R2 |

A business can connect its **own** payment, invoicing or messaging provider.

### 7.5 Security and privacy

- **Business isolation:** every database row belongs to a business and is blocked both in the server and in the database itself (RLS: a database rule that stops one business from seeing another's data). The same between branches.
- Two-factor authentication, passwords of at least 10 characters, sign-out after inactivity.
- ID numbers are encrypted, shown masked, and every view is logged.
- An audit log for each business and for the MyBiz team.
- Israeli Privacy Protection Law amendment 13: export and deletion on request, a data inventory, a security procedure, an appointed officer (still to be appointed).
- Security and accessibility scans that block merging.

### 7.6 Retention and background jobs

Leads, requests and AI chats: 12 months. Messages and the audit log: 24 months. Invoices: 7 years. A closed business is deleted after 90 days (today it only reports, it does not delete, by the owner's decision). Daily and hourly jobs: reminders, business billing and collection, messages, documents, payroll, shifts, AI tasks.

### 7.7 Technology in one sentence

Website in Next.js, app in Expo, server in Python (FastAPI), Postgres database on Supabase. Everything in one GitHub repository (`MyBiz-app/business-os`). Money is stored in minor units with a currency; times in UTC and displayed in the business's time zone. Every change goes through CI (automatic tests that run on every change).

---

## 8. Status and what is missing

The full, current status is in [`docs/STATUS.md`](../../STATUS.md). In short, as of 19 October 2026:

- **Built:** everything described in this spec is built in code and merged to `main`.
- **Built but off until go-live:** payments (#46), provider invoicing (#47), real AI in production, OpenAI / Gemini, email from our own domain, WhatsApp / SMS, the R2 second backup, virus scanning. Every item with a cost is switched on only by the owner's decision.
- **Missing in the product:** tools for 8 AI-agent data domains; the "strong" AI tier does not reach Opus in the business assistant; a business has no "country" field; no knowledge library for agents; console gaps (see the agents and console plan); the app has no screen for the 2FA "confirm the risk" message; the cancellation policy is not shown before joining; the 2FA sign-up e2e check is not wired into CI; no "guest" for a class without an account.
- **Not in code (waiting for the owner or professionals):** a lawyer for the legal texts, an accountant for payroll rates, appointing a data security officer, a manual accessibility pass, the final brand name (#36), real company details, a real backup-restore and rollback drill, a professional penetration test.

## 9. Document layout

```
docs/
  README.md / README.he.md      map of the documents
  STATUS.md / STATUS.he.md      status board
  DECISIONS.md                  decision log
  spec/current/                 the live spec (v4): system.en.md, system.he.md
  spec/archive/                 v1, v2, v3 and old Word files
  plans/                        the approved spec of each round (Hebrew)
  proposals/ (open, done)       design proposals per feature
  reviews/ (current, archive)   architecture reviews
  guides/                       guides (design, verticals, integrations, Claude Code and more)
  deploy/  legal/  store/  runbooks/
```

Rules: nothing is deleted, old material moves to the archive with `git mv`; every link in the docs is checked automatically (`node scripts/check-doc-links.cjs`); a round's new spec is saved in `docs/plans/` in that round's first PR; the Word files are regenerated from v4 with `node scripts/spec-to-docx.cjs he|en`.
