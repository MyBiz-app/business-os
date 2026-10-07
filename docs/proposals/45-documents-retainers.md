# Documents, retainers and time-based billing (#45)

Status: **DECIDED (delegated)**, 2026-10-07: the owner asked to keep building without stopping;
these are Claude's recommendations (decision X14 in [`DECISIONS.md`](../DECISIONS.md)).
Phase 7, last capability. Opens **Professional services** (beta): consultants, accountants,
lawyers, agencies.

## The need

An accountant or a consultant doesn't sell classes or slots. They keep each client's documents
(a contract to sign, a report, the client's own papers), log the time they work for each client,
and bill monthly: a fixed retainer that covers some hours, and the hours beyond it, or simply
hours × rate.

## Model

- **Documents** (`app.client_documents`): files on the client's card (contract, report, the
  client's papers…), kept through the storage provider (X13; built in: the database, up to
  10 MB per file). Staff choose what the client sees in the app; the client uploads the papers
  the business asks for. A document can ask for the client's signature: the client signs by
  writing their name (name and time recorded, like accepting a quote).
- **Time entries** (`app.time_entries`): who worked, for which client, the day, minutes, what was
  done, billable or not. Staff log their own; managers see everyone's.
- **Retainer** per client (`app.retainers`): a monthly fee, the minutes it includes and the
  hourly rate beyond them (or only an hourly rate).
- **Bills**: "bill the month" turns a client's retainer and unbilled time into a bill. A bill is
  a quote of kind `bill` (#44): numbered, lines, a private link — already accepted, the whole
  amount due — so the client pays it the same way (payments provider, receipt). Billed time
  entries point to their bill and are never billed twice.

## Screens

- Business web: on the client card — documents (upload, share, ask to sign), time (log, list,
  unbilled total), retainer, "bill the month"; "My time" for each staff member.
- Client app: My documents (view, upload, sign) and bills under My quotes.
- Business app: log time on the client card.

## Slices

1. DB + API: documents (upload, download, share, sign), time entries, retainers, bills from
   time, tests.
2. Business web: the client card sections, My time, billing a month.
3. Apps: client app documents and bills; business app time logging.
4. Professional services opens (beta) with its pack and a demo.
