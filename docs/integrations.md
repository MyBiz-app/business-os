# Integrations: adding or switching a provider

Every outside service sits behind one interface (decision X13,
[proposal](proposals/integrations.md)). Switching vendor never touches the rest of the system:
it is a new provider class, or a different choice in settings.

## Where things are

| Capability | Interface (`apps/api/app/providers/`) | Built in | Who chooses |
|---|---|---|---|
| Payments | `payments.py`: `PaymentProvider` — `create_checkout`, `parse_webhook`, `refund` | `simulated` | each business (settings → Integrations), else `API_PAYMENTS_PROVIDER` |
| Invoicing | `invoicing.py`: `InvoiceProvider` — `issue` | `internal` (MyBiz receipts) | each business, else `API_INVOICING_PROVIDER` |
| Messaging | `messaging.py`: `MessageProvider` — `send` | `simulated` | each business, else `API_MESSAGING_PROVIDER` |
| Email | `email.py` (senders in `app/messaging/email.py`) | `log` | the platform: `API_EMAIL_PROVIDER` |
| AI | `ai.py` (`app/ai/gateway.py`) | `demo` | the platform: `API_ANTHROPIC_API_KEY` |
| Storage | `storage.py`: `StorageProvider` | `database` | the platform: `API_STORAGE_PROVIDER` |

- `registry.py`: `@register(capability, name, label, fields=…)` and `SettingField`.
- `choice.py`: `choose(db, tenant_id, capability)` — the business's own connection, else the
  platform default — returns the provider instance. Everything else calls this.
- `secrets.py`: business secrets are encrypted with `API_SECRETS_KEY` (a Fernet key; required
  outside local development) and never returned by the API.
- `app/messaging/outbox.py`: the `send-messages` and `issue-documents` jobs hand work to each business's
  provider and keep failures for a retry (up to 5 attempts).
- `app/api/webhooks.py`: `POST /webhooks/payments/{provider}/{tenant_id}`; the provider verifies
  the signature, then the checkout is completed for exactly its amount.
- `app/api/integrations.py`: settings → Integrations (`/integrations`) and the console
  (`/platform/integrations`).

## Adding a provider (for example invoicing provider "acme")

1. Create `apps/api/app/providers/acme_invoicing.py`:

   ```python
   from app.providers.invoicing import InvoiceDocument, IssuedDocument, InvoicingUnavailable
   from app.providers.registry import SettingField, register

   @register(
       "invoicing", "acme", "Acme invoices",
       fields=(SettingField("api_key", "API key", secret=True),
               SettingField("business_id", "Business number")),
   )
   class AcmeInvoices:
       def __init__(self, settings: dict[str, str]) -> None:
           self.api_key = settings["api_key"]
           self.business_id = settings["business_id"]

       def issue(self, document: InvoiceDocument) -> IssuedDocument:
           # Call Acme's API with document.lines, document.total, document.client_name…
           # Raise InvoicingUnavailable on a temporary failure (the job retries).
           ...
           return IssuedDocument(number="…", url="https://…/doc.pdf", provider_ref="…")
   ```

2. Import it in `apps/api/app/providers/choice.py` (the import list at the top) so it registers.
3. Write `tests/test_acme_invoicing.py` with recorded responses (no network in tests).
4. That's all: it appears in settings → Integrations for every business, with its fields; the
   console lists it; `API_INVOICING_PROVIDER=acme` makes it the platform default.

A payments provider also implements `parse_webhook` (verify the signature with the business's
secret; raise `WebhookRejected` otherwise) and is given its webhook address
`{API}/webhooks/payments/{name}/{tenant_id}` in the provider's dashboard.

## Switching provider

- **A business**: settings → Integrations → choose another provider and fill its settings.
  New payments, documents and messages use it from that moment; history stays as it was
  (each payment, receipt and message keeps the provider that handled it).
- **The platform default**: change `API_<CAPABILITY>_PROVIDER` (and `API_<CAPABILITY>_SETTINGS`,
  a JSON object of its settings) in the environment and restart the API.
