# Integrations: adding or switching a provider

Every outside service sits behind one interface (decision X13,
[proposal](../proposals/done/integrations.md)). Switching vendor never touches the rest of the system:
it is a new provider class, or a different choice in settings.

## Where things are

| Capability | Interface (`apps/api/app/providers/`) | Built in | Who chooses |
|---|---|---|---|
| Payments | `payments.py`: `PaymentProvider` - `create_checkout`, `parse_webhook`, `refund` | `simulated` | each business (settings → Integrations), else `API_PAYMENTS_PROVIDER` |
| Invoicing | `invoicing.py`: `InvoiceProvider` - `issue` | `internal` (MyBiz receipts) | each business, else `API_INVOICING_PROVIDER` |
| Messaging | `messaging.py`: `MessageProvider` - `send`; a WhatsApp provider also implements `parse_inbound` (verify the notification, return `IncomingMessage`s) to feed the AI replies via `/webhooks/whatsapp/{provider}/{tenant_id}` | `simulated` | each business, else `API_MESSAGING_PROVIDER` |
| Email | `email.py` (senders in `app/messaging/email.py`) | `log` | the platform: `API_EMAIL_PROVIDER` |
| Push notifications | `app/messaging/push.py` (Expo push; phones register via `PUT /me/push-tokens`) | `expo` | the platform: `API_PUSH_PROVIDER` (`expo` / `log` / `off`), optional `API_EXPO_ACCESS_TOKEN` |
| AI | `ai.py` (`app/ai/gateway.py`) | `demo` | the platform: `API_AI_PROVIDER` (`anthropic` / `openai` / `gemini`), the vendor's key, and `API_AI_ENABLED_VENDORS` for non-Anthropic vendors |
| Storage | `storage.py`: `StorageProvider` - `put`, `get`, `delete`, `signed_url` | `database` (also `supabase`: Supabase Storage, T80) | the platform: `API_STORAGE_PROVIDER` |
| Embeddings (search by meaning for the console agents' libraries) | `app/ai/embeddings.py`: `EmbeddingProvider` - `embed(texts, query=...)` | none: **off** (`voyage` is built) | the platform: `API_KB_EMBEDDINGS_PROVIDER` (`off` / `voyage`) and `API_VOYAGE_API_KEY` |

- `registry.py`: `@register(capability, name, label, fields=…)` and `SettingField`.
- `choice.py`: `choose(db, tenant_id, capability)` - the business's own connection, else the
  platform default - returns the provider instance. Everything else calls this.
- `secrets.py`: business secrets are encrypted with `API_SECRETS_KEY` (a Fernet key; required
  outside local development) and never returned by the API.
- `app/messaging/outbox.py`: the `send-messages` and `issue-documents` jobs hand work to each business's
  provider and keep failures for a retry (up to 5 attempts).
- `app/api/webhooks.py`: `POST /webhooks/payments/{provider}/{tenant_id}`; the provider verifies
  the signature, then the checkout is completed for exactly its amount.
- `app/api/integrations.py`: settings → Integrations (`/integrations`) and the console
  (`/platform/integrations`).

## File storage (Supabase Storage)

Client documents go to a private Supabase Storage bucket when the platform's storage provider is
`supabase` (decision T80). To turn it on for a deployment:

1. The bucket: `files`, private, 10 MB per file (created on staging 2026-10-11; locally it comes
   from `supabase/config.toml`).
2. On the API host: `API_STORAGE_PROVIDER=supabase` and
   `API_STORAGE_SETTINGS={"url": "https://<project>.supabase.co", "service_key": "<secret key>"}`
   (the secret key from Supabase → Project Settings → API Keys; it never goes in the repository).
3. Move documents already kept in the database: `uv run python -m app.jobs move-files`, again
   until it reports `left: 0`.

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

## Social networks (content studio)

Social networks are read through their own small registry, not the capability registry above,
because one business connects several accounts of several networks. A provider is a class in
`apps/api/app/social/` that implements `SocialProvider` (`authorize_url`, `exchange_code`,
`refresh`, `fetch_account_metrics`, `fetch_posts`, `fetch_audience`) and is registered with
`register_social(...)`. The networks the studio shows are listed in `NETWORKS`
(`app/social/providers.py`): a network whose provider is not registered shows as "coming soon".
Tokens are stored encrypted (`app/providers/secrets.py`) and only summarized, public numbers of
the business's own accounts are kept. The `demo` provider gives believable numbers without any
account.

The Meta provider (`app/social/meta.py`, Facebook Pages + Instagram as `meta`, Threads as
`threads`) is the first real one. It is configured by `API_META_APP_ID` / `API_META_APP_SECRET`
(Threads: `API_META_THREADS_APP_ID` / `API_META_THREADS_APP_SECRET`, `API_META_GRAPH_VERSION`
for the Graph API version); a provider with a `configured()` method stays "coming soon" until it
returns true. Register `{API}/social/callback/meta` (and `/social/callback/threads` for Threads)
as the OAuth redirect URI at the network. Optional `publish(account, text, image_url)` on a
provider enables `POST /social/accounts/{id}/publish`; a provider raises `NeedsReauth` when a
token is refused and the account is then marked "needs reconnect".

Google and TikTok connectors: `youtube` and `google_business` (`app/social/google.py`, one Google
OAuth client) and `tiktok` (`app/social/tiktok.py`); `x`, `linkedin`, `pinterest` and `snapchat`
are disabled adapters (`app/social/soon.py`). Environment: `API_GOOGLE_OAUTH_CLIENT_ID` /
`API_GOOGLE_OAUTH_CLIENT_SECRET`, `API_TIKTOK_CLIENT_KEY` / `API_TIKTOK_CLIENT_SECRET`; without
them the networks stay "coming soon". Redirect URIs to register: `{API_API_URL}/social/callback/youtube`
and `/social/callback/google_business` (both in the same Google OAuth client) and
`/social/callback/tiktok`. Google scopes: `youtube.readonly`, `yt-analytics.readonly`,
`business.manage` (Business Profile APIs need Google's access approval). TikTok scopes:
`user.info.basic`, `user.info.stats`, `video.list`; TikTok keeps no daily history, so followers
build up from our own daily reads. These tokens expire within a day, so the sync renews them on
every run. Publishing is not built for these networks yet.

## Cities, streets and map points (addresses)

Addresses are chosen from the official Israeli lists (data.gov.il, free open data), kept as a
snapshot in the code (`apps/api/app/geo/data/il_geo.json.gz`) and loaded into the shared, read-only
tables `geo_cities` and `geo_streets` by migration 0129. Refresh once a year:
`uv run python scripts/build_geo_snapshot.py` (needs access to data.gov.il), review the printed
counts, commit the file, then `uv run python -m app.geo.loader` against each database (rows are
inserted or updated, never deleted: saved addresses point at them).

City centers (the point of each city on the map) are stored in `geo_cities.latitude/longitude`,
loaded from `apps/api/app/geo/data/il_city_centers.json` by migration 0153 and by
`python -m app.geo.loader`. The file is built by `PYTHONPATH=. uv run python
scripts/build_geo_centers.py` from the GeoNames Israel dump (free, CC BY 4.0, credit
"GeoNames, geonames.org"): cities are matched by name, and a city GeoNames does not know gets the
middle of its region, marked `center_source = 'region'`. Rerun it after refreshing the city snapshot.
No request leaves the system when a city center is needed, and a client's address is never sent to
an outside service.

A branch's point on the map comes from OpenStreetMap's free Nominatim service
(`app/geo/geocoder.py`): one request when a branch address is saved, never per page view, with
an identifying `User-Agent` (`API_GEOCODER_USER_AGENT`). `API_GEOCODER=none` turns it off (tests
and local work). A failure never blocks saving; the branch simply has no point until the next
save or until the pin is placed by hand. Nominatim's policy allows light use (about one request a
second); if branch saves ever become frequent, host Nominatim or switch the class behind
`get_geocoder()` for another service.

## Switching provider

- **A business**: settings → Integrations → choose another provider and fill its settings.
  New payments, documents and messages use it from that moment; history stays as it was
  (each payment, receipt and message keeps the provider that handled it).
- **The platform default**: change `API_<CAPABILITY>_PROVIDER` (and `API_<CAPABILITY>_SETTINGS`,
  a JSON object of its settings) in the environment and restart the API.

## Branches map (OpenFreeMap)

The branches map and the branch pin use MapLibre with free OpenFreeMap vector tiles
(`tiles.openfreemap.org`, OpenStreetMap data, no key, no sign-up, credit shown on the map). The
library loads only on the map page, the dashboard map card and the branch editor. The browser
fetches tiles itself, so `connect-src` and `img-src` in `apps/web/src/lib/csp.ts` list that host
(`MAP_ORIGIN`) and `worker-src` allows blobs. To switch provider (for example MapTiler, free up
to 100,000 loads a month), change the two style URLs in `components/branch-map/map-core.ts` and
`MAP_ORIGIN`.

MapLibre 6 starts its worker from a file next to its own script, which a bundler cannot give it, so
`scripts/copy-maplibre-worker.mjs` (run by `dev` and `build`) copies the worker to
`apps/web/public/maplibre/` and `loadMaplibre()` in `map-core.ts` points the library there. Load
the library only through `loadMaplibre()`.
