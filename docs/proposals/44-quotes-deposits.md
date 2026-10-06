# Quotes, deposits and event projects (#44)

Status: **DECIDED (delegated)**, 2026-10-07: the owner asked to keep building without stopping;
these are Claude's recommendations (decision X12 in [`DECISIONS.md`](../DECISIONS.md)).
Phase 7, fourth capability. Opens **Creative & events** (beta): photographers and studios, DJs,
event suppliers, small venues. Also serves Home & field services (a quote before a big job).

## The need

A wedding photographer doesn't sell a class or a slot: they send a quote (a package, extra
hours, an album), the couple accepts it, pays a deposit to hold the date, and the rest closer to
the event. An air-conditioning installer quotes before installing. Today a business can only
sell plans and take bookings.

## Model

- **Quote** (`app.quotes`): for a client, with a number per business (like receipts: 1001,
  1002…), a title, lines (description, quantity, unit price), a total in the business currency,
  an optional event (date and time, place), valid until a date, notes / terms, and a **deposit**
  (a percentage of the total, 0 for none).
- **Statuses**: draft → sent → accepted or declined; a sent quote past its date is expired.
  Only a draft can be edited; changing a sent quote means a new version (copy as a draft).
- **The client sees and accepts it** by a private link (a long random token, no sign-in) or in
  the client app. Accepting asks for their name (a simple acceptance record: name, time).
- **Deposit and balance**: on acceptance the deposit is due; the client pays it from the quote
  page (simulated until a payment provider is chosen, #46) and gets a receipt
  ("Deposit · Quote 1002"). Staff record the balance (or any part) at the venue. The quote shows
  paid and due.
- **Event project**: an accepted quote with an event date is the event's project: it shows in
  an "Events" list by date and on the client's card. (A calendar entry for the event, and
  assigning staff to it, come later.)

## Screens

- Business web: Quotes (list by status, new quote editor with lines, send = copy link or a
  WhatsApp message, copy as a new version), the quote on the client card, Events by date.
- Public quote page (web): the quote, accept with a name, pay the deposit, receipt.
- Client app: My quotes (view, accept, pay the deposit). Business app: quotes on the client card.

## Slices

1. DB + API: quotes and lines, numbering, statuses, the public link (view, accept, pay the
   deposit), payments for a quote and receipts, tests.
2. Business web: quotes list and editor, sending, the client card, events by date; the public
   quote page.
3. Apps: client app (my quotes, accept, pay); business app (quotes on the client card).
4. Creative & events opens (beta) with its pack and a demo.
