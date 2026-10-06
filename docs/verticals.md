# Industries: categories and sub-categories

MyBiz serves every industry from one core. What differs between industries (the word for clients,
how they book, policies, the client details a business keeps, starter services and plans, the
recommended modules and the marketing texts) is configuration in one catalog, not code. The spec
describes the product side (section 4); this page is the how-to.

## Where things are

| What | Where |
|---|---|
| The catalog: one file per category, with its sub-categories under `children` | `packages/verticals/catalog/*.json` |
| Types, inheritance and lookups for the web and the apps | `packages/verticals/src/index.ts` |
| Copies the rest of the system reads (generated, checked in) | `packages/verticals/src/catalog.generated.ts`, `apps/api/app/verticals_catalog.json` |
| The API's view (packs used when a business is created, client fields, health forms) | `apps/api/app/verticals.py` |
| Texts: name, tagline, benefits, industry page, "your studio", an example name | `verticals.<key>` in `packages/i18n/messages/{he,en}.json` |
| Industry words in the interface (clients, schedule, …) | `terms.<set>` in the translations |
| Client field labels and their choices | `clientFields.<key>`, `clientFields.<key>_options.<option>` |
| Icons (catalog name → icon) | `apps/web/src/components/vertical-icon.tsx` |

## How inheritance works

A **category** sets everything. A **sub-category** lists only what differs and inherits the rest
from its parent (sub-categories can have sub-categories of their own):

- Settings (`terms`, `client_term`, `booking_modes`, `cancellation_window_minutes`,
  `booking_requires_plan`, `health_form`, `default_preset`, `recommended_modules`, `icon`,
  `color`): the entry's own value, else the parent's.
- `default_services`, `default_plans`, `default_rooms`: the entry's own list replaces the parent's.
- `client_fields` replaces the parent's fields; `extra_client_fields` adds to them.
- Texts: `verticals.<key>.<text>` from the entry, else from the nearest parent that has it. A
  sub-category needs only `name` and `tagline`.

A service with `"booking_mode": "resource"` is a court or room rented by the hour: its
`duration_minutes` is the shortest length, `max_minutes` and `step_minutes` the others, and its
`prices` are per hour. Such an industry lists `default_rooms` (names, capacity, `opens` and
`closes`): a new business gets them in its main branch, for rent every day in those hours and
serving its resource services, so it can take reservations from the first minute.

Prices are integer minor units per currency. `ILS` is required; `USD` and `EUR` default to rough
equivalents. A business keeps the key it chose (category or sub-category) in `tenants.vertical`.

## Statuses

| Status | Meaning |
|---|---|
| `live` | Open for sign-up everywhere |
| `beta` | Open for sign-up, new |
| `planned` | Shown on the website as "coming soon" with "tell me when"; closed for sign-up |

## Adding a category or a sub-category

1. Scaffold it. The entry starts as `planned`, so nothing opens by accident:
   ```
   pnpm vertical:new kickboxing --parent classes   # a sub-category
   pnpm vertical:new bakery                        # a new category (its own file)
   ```
2. Fill in the catalog entry: starter services and plans, client fields, policies. For a new
   category, also choose an icon, add `terms.<key>` to both translation files (copy an existing
   set and adapt the words), and add labels for any new client fields under `clientFields`.
3. Replace every `TODO` text under `verticals.<key>` in Hebrew and English.
4. Set `"status": "live"` (or `"beta"`), then:
   ```
   pnpm verticals:export
   pnpm --filter @business-os/verticals test
   ```
   The tests name anything missing: texts in both languages, words, field labels, prices, a known
   preset and parent, leftover TODOs, and out-of-date copies.

From there it appears by itself on the marketing site (home, `/industries`, its own page,
footer, sitemap), in the sign-up journey, in onboarding, in the contact form, in the console and
in the apps. The API test `test_every_open_industry_starts_a_business` creates a business for
every open entry.

A category that needs something the core cannot do yet (jobs at the client's address, pets under
an owner, quotes and deposits) stays `planned` until that capability is built: see spec section
4.3 and the phase 7 issues. Courts and rooms by the hour are built (#41): Sports & facilities is
open as beta.
