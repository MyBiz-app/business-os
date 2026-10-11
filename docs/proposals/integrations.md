# Integrations: swappable providers (X13)

Status: **DECIDED (delegated)**, 2026-10-07. The owner asked for every outside service to be
"easy to swap": if invoicing provider X is chosen today and Y is cheaper tomorrow, switching is a
small, local change. Connecting the real providers is the last step (go-live, #34); until then
the built-in simulated providers keep everything working.

## One shape for every capability

Each outside capability has, in `apps/api/app/providers/`:

1. **An interface** (a Python `Protocol`) in the system's own words, never a vendor's:
   payments create a hosted checkout and read the provider's webhook; invoicing issues a legal
   document for a receipt; messaging sends a WhatsApp / SMS message; email sends an email; AI
   answers with tools; storage keeps files.
2. **Built-in providers** that work with no account: `simulated` payments, `internal` receipts,
   `simulated` messages, `log` email, the demo AI, `database` storage.
3. **A registry**: a provider is a class registered under a name, with the settings it needs
   (name, label, secret or not). Adding vendor X = one file with one class + `@register("x")`.
   Nothing else in the system names a vendor.
4. **The choice**: the platform's default per capability (environment, e.g.
   `API_INVOICING_PROVIDER=x`), and, for capabilities where each business has its own account
   (payments, invoicing, messaging), the business's own connection, chosen and filled in
   settings → Integrations. A business without one uses the platform default.

## Where the choice is used

- **Payments**: checkouts ask the business's payments provider for a hosted payment page; the
  provider's webhook arrives at `/webhooks/payments/{provider}` and completes the checkout.
  Simulated checkouts keep working as today.
- **Invoicing**: every receipt is a document to issue. Receipts keep their own number; a job
  (`issue-documents`) sends each to the business's invoicing provider and stores the legal
  document's number and link (`internal` keeps the receipt as the document).
- **Messaging**: messages go to an outbox; the business's messaging provider sends them
  (`send-messages` job) and records the provider's id and status. `simulated` marks them sent.
- **Email, AI**: already behind interfaces (`app/messaging/email.py`, `app/ai/gateway.py`); they are
  registered the same way.

## Secrets

A business's provider secrets (API keys, terminal passwords) are encrypted in the database
with the platform's key (`API_SECRETS_KEY`, kept in the provider secret store) and never
returned by the API; the screens show only "set". Platform-level secrets stay in environment
variables.

## Adding a provider

See [`docs/integrations.md`](../integrations.md): write the class, register it, add its
settings, add its webhook handling if any, write a test with recorded responses.
