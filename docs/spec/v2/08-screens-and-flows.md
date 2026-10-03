# 08 — Screens & User Flows

Screen inventory for the prototype (Phase 1), grouped by side of the platform. Each screen lists
the sprint that delivers it. Screen IDs are stable references for tickets, routes and tests.

Every screen must work in Hebrew (RTL) and English (LTR), light and dark mode, keyboard and screen
reader. Labels such as "client" / "member" come from the vertical pack, never hard-coded.

## Business side — web (primary) + mobile (on the go)

| ID | Screen | Purpose | Sprint |
|---|---|---|---|
| AUTH-1 | Sign up | Email + password, accept terms | 1 |
| AUTH-2 | Verify email | "Check your inbox" + resend | 1 |
| AUTH-3 | Log in | Email + password | 1 |
| AUTH-4 | Forgot / reset password | Request link, set new password | 1 |
| AUTH-5 | Business switcher | Pick a business when the user belongs to several | 1 |
| ONB-1 | Create business (minimal) | Name, vertical, language, time zone, currency | 1 |
| ONB-2 | Questionnaire | Size, needs → recommended bundle | 5 |
| ONB-3 | Plan configurator | Toggle modules, live price | 5 |
| ONB-4 | Branding | Logo, colors, cover image, live preview of client app | 2 |
| HOME-1 | Dashboard (shell) | Today's sessions, quick actions; KPIs arrive in Sprint 6 | 1 (shell) · 6 |
| CLI-1 | Clients list | Search, filter, status | 2 |
| CLI-2 | Client profile | Details, bookings, memberships, notes | 2 · 3 · 4 |
| STF-1 | Staff list + invite | Invite by email, assign role | 2 |
| STF-2 | Roles & permissions | System roles + custom role toggles | 2 |
| SRV-1 | Services | Classes / appointment types, duration, capacity, price | 2 |
| LOC-1 | Locations & rooms | Addresses, rooms, opening hours | 2 |
| SCH-1 | Schedule (calendar) | Day / week view, sessions with capacity | 3 |
| SCH-2 | Session editor | One-off or recurring, instructor, room, capacity | 3 |
| SCH-3 | Session detail | Roster, waitlist, check-in, add / remove client | 3 |
| PLN-1 | Plans | Memberships and punch cards catalog | 4 |
| PLN-2 | Sell / assign plan | Assign to client (payment simulated) | 4 |
| AI-1 | AI assistant | Chat panel; answers via tools; pending action cards | 6 |
| SET-1 | Business settings | Profile, language, time zone, appearance, modules | 1 (basic) · 5 |
| ME-1 | My account | Name, language, theme, password | 1 |

## Client side — shared mobile app (branded per business) + web booking page

| ID | Screen | Purpose | Sprint |
|---|---|---|---|
| C-AUTH-1 | Sign up / log in | Same identity system as business side | 1 |
| C-JOIN-1 | Join business | Via link / QR code; shows business branding | 3 |
| C-HOME-1 | Branded home | Next booking, quick "book a class", announcements | 3 |
| C-SCH-1 | Schedule | Browse sessions by day, filter by service / instructor | 3 |
| C-BOOK-1 | Book / cancel / waitlist | Respect capacity, cancellation window, entitlements | 3 · 4 |
| C-MY-1 | My bookings | Upcoming + history | 3 |
| C-PLN-1 | My plans | Active membership / punch card, remaining credits | 4 |
| C-PRF-1 | Profile | Details, language, theme, switch business | 3 |

## Platform side — web console

| ID | Screen | Purpose | Sprint |
|---|---|---|---|
| P-1 | Businesses list | Status, vertical, plan, created date | 5 |
| P-2 | Business detail | Modules, usage meters, support access (audited) | 5 |
| P-3 | Usage overview | AI credits, messages, storage per business | 5 |

## Core user flows

### F1 — Owner signs up and creates a business (Sprint 1)

```
AUTH-1 Sign up → AUTH-2 Verify email → AUTH-3 Log in
  → (no business yet) ONB-1 Create business → HOME-1 Dashboard
  → (has businesses) AUTH-5 Business switcher → HOME-1 Dashboard
```

Result: `user`, `tenant`, `tenant_membership(role=owner)`; vertical pack defaults applied.

### F2 — Owner sets up the business (Sprint 2)

```
HOME-1 → SET-1 / ONB-4 Branding → LOC-1 Locations → SRV-1 Services
       → STF-1 Invite staff → STF-2 Roles → CLI-1 Add clients
```

### F3 — Owner builds the schedule (Sprint 3)

```
SCH-1 Calendar → SCH-2 New session (recurring weekly, capacity 12) → SCH-1 shows occurrences
```

### F4 — Client joins and books (Sprint 3–4)

```
QR / link → C-JOIN-1 (branded) → C-AUTH-1 → C-HOME-1 → C-SCH-1 → C-BOOK-1
  → full? → join waitlist → notified when a spot opens
  → no valid plan? → "you need a plan" (Sprint 4)
```

### F5 — Front desk runs a session (Sprint 3)

```
SCH-1 → SCH-3 Session detail → check in clients / add walk-in → mark no-shows
```

### F6 — Owner asks AI and confirms an action (Sprint 6)

```
AI-1 "How many no-shows last week?" → read tool → answer with numbers
AI-1 "Book Dana into tomorrow's 18:00 pilates" → pending action card (preview)
  → Confirm → server re-validates (capacity, plan, permissions) → executes → audit log
```

## Navigation shells

- **Business web:** side navigation (start-side in RTL / LTR automatically), top bar with business
  switcher, AI button, user menu. Items appear only for enabled modules and granted permissions.
- **Business mobile:** bottom tabs — Today, Schedule, Clients, More.
- **Client mobile:** bottom tabs — Home, Schedule, My bookings, Profile. Colors and logo from the
  business's branding.
