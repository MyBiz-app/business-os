# 01 — Product Scope

## Vision

One platform where a small business runs customers, staff, schedule, sales, payments, marketing and
analytics — and can "hire" AI agents that answer questions and perform confirmed actions.
Above all businesses sits our Platform layer, managed with the same principles.

**Positioning:** a familiar category done better — more beautiful, faster, AI built in — at a lower
price, because the owner pays only for what they use.

## Sides of the platform

| Side | Users | Surfaces |
|---|---|---|
| Platform | Platform owner, later internal staff | Web (platform console) |
| Business | Owner, managers, staff | Web (primary), mobile (on the go) |
| Client | The business's customers | Mobile app (shared, branded per business), web booking page |

A single user can be staff in one business and a client in another (or the same) business.

## Roles and permissions

- Permissions are fine-grained keys defined in code (e.g. `bookings.create`, `payments.refund`).
- Roles are named bundles of permissions per tenant. System role templates: Owner, Manager, Staff,
  Front desk. Owners can create custom roles with a toggle UI.
- Platform roles are separate: Platform owner, Support, Sales (future).
- Support access to a tenant is explicit, time-limited and audited.

## Key flows

1. **Onboarding (configurator):** sign up → verify email → questionnaire (vertical, size, needs)
   → recommended bundle → customize modules with live price → branding (logo, colors, images)
   → language and appearance → business is provisioned with vertical defaults.
2. **Operate:** clients, staff, services, schedule, bookings, memberships, payments.
3. **Client:** joins business via link/QR → branded home → schedule → book / cancel / waitlist
   → memberships → profile.
4. **AI:** owner asks questions → agent answers via tools → owner requests action → pending
   action preview → confirm → server re-validates and executes → audit log.
5. **Platform:** see businesses, status, plans, usage, MRR.

## Prototype scope (fake data, real registration)

| Area | In prototype |
|---|---|
| Auth | Real sign-up, email verification (dev mailbox), login, password reset |
| Business | Create business via configurator, branding, staff + roles, services, schedule, bookings, clients, memberships |
| Client | Branded mobile app: home, schedule, book/cancel, profile |
| AI | Q&A over business data via tools; at least one confirmed action (e.g. book a client) |
| Platform | Businesses list, status, modules, usage |
| Quality | Hebrew + English, light + dark, basic accessibility checks, tenant-isolation tests |

**Simulated in prototype:** payments, WhatsApp, invoices, Meta/Google, app-store release.

## MVP additions (first real business)

Real payment provider, real email, data import (CSV / Excel), health declaration + digital
signature, membership freeze, punch cards, basic analytics dashboard, backups, monitoring,
security review, privacy policy and terms.

## Israel-specific requirements

| Requirement | Notes |
|---|---|
| Health declaration | Legally required for fitness; digital form + signature, stored per client |
| Membership freeze | Pause entitlement and extend end date |
| Punch cards | Credit-based entitlements alongside recurring memberships |
| Standing order / recurring card charge | Via payment provider tokenization |
| Invoices / receipts | Via invoicing provider, incl. Israel Tax Authority allocation numbers when required |
| Privacy | Privacy Protection Law, Amendment 13; GDPR when serving EU |
| Accessibility | IS 5568 (based on WCAG 2.x AA) for web; equivalent care on mobile |
