# Dependents: pets under an owner, children under a parent (#43)

Status: **DECIDED (delegated)**, 2026-10-06: the owner asked to keep building without stopping;
these are Claude's recommendations (decision X10 in [`DECISIONS.md`](../DECISIONS.md)).
Phase 7, second capability. Opens **Pet services** (beta) and lets Kids & Youth businesses keep
a profile per child.

## The need

A dog groomer's client is the owner, but the appointment is for Rex, and what matters is Rex's
breed, size and temperament. A kids' activity is booked and paid by a parent for one or two of
their children. Today a client is one person who books for themselves.

## Model

- **Dependent**: a profile under a client (`app.dependents`): name, kind (`pet` or `child`), birth
  date, the industry's details (like client fields: species, breed, size, allergies…), notes,
  active. A client can have several. Tenant isolation and RLS as for clients; a client sees and
  edits only their own dependents in the app.
- **A booking can name a dependent** (`bookings.dependent_id`, which must belong to the booking's
  client). One live booking per client, session *and dependent*, so a parent can book two
  children into the same class and an owner two dogs into the same day.
- Payments, plans and receipts stay with the client (the payer); the dependent is who comes.

## Industry pack

A category says whether its clients have dependents and what they're called: `dependents`
(`pet` / `child`), the dependent fields (like `client_fields`) and `dependent_required` (a booking
must name one: true for pets). Words in the translations: "pet" / "child".

## Screens

- Business web and app: the client card lists the dependents (add, edit); booking (a class, an
  appointment, a court) picks the dependent; rosters and the schedule show "Rex · Dana Levi".
- Client app: "My pets" / "My children" in the profile; booking asks who it's for.

## Slices

1. DB + API: dependents, booking a dependent, the pack settings, tests.
2. Business web: dependents on the client card, picking one when booking, rosters.
3. Client app: my pets/children, booking for one; business app: rosters and the client card.
4. Pet services opens (beta) — grooming, training, daycare — with its pack and a demo.
