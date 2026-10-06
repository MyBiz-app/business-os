# Proposal: book courts, rooms and spaces by the hour (#41)

Status: **PROPOSED**, waiting for the owner (decision X9 in [`DECISIONS.md`](../DECISIONS.md)).
Phase 7, first capability. Opens the "Sports & facilities" category (today "coming soon").

## The need

A tennis or padel club, a football pitch, a rehearsal studio or a meeting-room space doesn't sell
a class or a person's time: it rents **a place for a stretch of time**. The client picks the
place (or just "a court"), the day, the start time and how long, sees the price and books.
Sometimes a staff member comes with it (a coach for the court), usually not.

## How it fits what exists

Appointments (decision of phase 4, migration 0027) already do almost all of this for **a
person's** time: weekly hours, free start times on a 15-minute grid, a one-person session created
by the server after checking the time is still free, then a normal booking, so check-in,
reminders, receipts, cancellations and reports just work.

A resource booking is the same thing for **a place's** time:

| | Appointment (exists) | Resource (proposed) |
|---|---|---|
| What is busy | a staff member | a room / court (`app.rooms`, already per branch) |
| Weekly hours | `staff_hours` | `room_hours` (new, same shape) |
| Length | the service's duration | chosen by the client: min, max and step from the service |
| Price | the plan / service price | price per hour × length (minor units + currency) |
| Staff | required | optional |
| What gets created | a one-person session + booking | the same, with `room_id` set |

So: a third `booking_mode` value, `resource`, on services ("Padel court", "Rehearsal room
A/B"), linked to the rooms that can serve it.

## Data (one migration)

- `app.rooms`: add `bookable boolean` (default false), keep `capacity` (players / people).
- `app.room_hours` (new): `room_id, weekday, starts, ends`, like `staff_hours`, with RLS.
- `app.services`: allow `booking_mode = 'resource'`; add `min_minutes`, `max_minutes`,
  `step_minutes` (e.g. 60 / 120 / 30) and `price_per_hour` (minor units, the business currency).
- `app.service_rooms` (new): which rooms serve which resource service.
- **No double booking, guaranteed by the database**: an exclusion constraint on
  `(room_id, tstzrange(starts_at, ends_at))` for scheduled sessions (`btree_gist`), on top of the
  server's check, so two people pressing "book" at the same second can't both get the court.

Tenant isolation, money in minor units and UTC times stay exactly as today.

## Flows

- **Client app**: "Book a court" → the kind (padel / tennis), day strip, length (1h, 1.5h, 2h),
  free start times across the business's courts (or a chosen one), price, pay (simulated, like
  plans today) or "pay at the venue" (a business setting), confirm.
- **Business web**: a day grid (resources × hours) to see and add reservations (phone and
  walk-in), move or cancel them; resource hours on each room.
- **Business app**: the same day, as a list per court, with "new reservation".
- **Reports**: occupancy per resource and per hour (the existing heatmap, by resource).
- **AI assistant**: a "find a free court" tool, through the same server-side check.

## The category

Open **Sports & facilities** as *beta* with sub-categories: padel / tennis club, football
pitches, rehearsal / recording studios, meeting rooms & coworking. Words (`terms.sports`):
"players", "courts", "reservation". Demo generator: a padel club with 4 courts and a month of
reservations (fictitious data).

## Slices (each a PR, each end to end)

1. DB + API: rooms as resources, hours, resource services, free times, booking, exclusion
   constraint, tests (double-booking race included).
2. Business web: resource hours, the day grid, reservations.
3. Client app: booking a court with price and payment.
4. Business app + reports + AI tool.
5. The category opens (beta), its pack and a demo.

## Questions for the owner

1. **Reuse rooms as resources** (recommended: they already belong to a branch and appear in the
   schedule) or a separate "resources" table?
2. **Price per hour** with a minimum length (recommended), or fixed slots with a fixed price?
   Peak / off-peak prices: later?
3. **Payment**: must the client pay in the app to book, or may the business allow "pay at the
   venue"? (Recommended: a business setting, default "pay in the app".)
4. **Which sub-categories open first?** Recommended: padel / tennis and rehearsal rooms.
