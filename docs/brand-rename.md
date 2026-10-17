# Renaming the product in 30 minutes

"MyBiz" is a provisional name. Everything that spells it lives in **one file**,
[`packages/i18n/brand.json`](../packages/i18n/brand.json), and the rest is generated from it.
A test (`packages/brand/test/embedded-name.test.mjs`) fails when code writes the name anywhere
else, so a new name cannot leave a stray copy behind.

## What the file holds

| Field | Used for |
|---|---|
| `name`, `shortName` | Every screen, email, PDF and the app's store name |
| `domain`, `appUrl` | The public domain and the web address of the app |
| `app.scheme`, `app.legacySchemes` | The app's link scheme (`<scheme>://join?code=...`). Put the old scheme in `legacySchemes` and old links keep working |
| `app.cookiePrefix`, `app.storagePrefix` | Cookie and browser-storage names (neutral `bos`; leave them alone on a rename, changing them signs everyone out) |
| `emails` | Support, billing, sender and no-reply addresses |
| `social` | The footer's profile links |
| `legal` | Company name, number, address and document versions printed on invoices and legal pages |

## Steps

1. **Edit `brand.json`**: `name`, `shortName`, `domain`, `appUrl`, `emails`, `social`, and `legal`
   when the real company exists (turn `fictitious` off then).
2. **Run `pnpm brand:sync`.** It copies the file for the API image (`apps/api/app/core/brand.json`),
   rewrites the redirect list and invite subject in `supabase/config.toml`, the name, scheme and
   permission texts in `apps/client-app/app.json`, the API's exported translations and the
   Supabase email templates. Commit what it changed. `pnpm brand:sync --check` is what CI runs.
3. **Logo and icons.** The logo is drawn from the name: run `pnpm --filter @business-os/brand build:assets`.
   A new mark or color is a change to `packages/brand/src/index.ts`.
4. **Domain.** Point the new domain at Vercel (web) and Render (API), then set the sender domain
   in Resend (`docs/deploy/go-live-checklist.md`, email section).
5. **Supabase (hosted).** Run the *Apply auth settings* workflow so the new redirect list and email
   templates reach the project. Add the new scheme to `REDIRECT_URLS` in
   `.github/workflows/auth-settings-staging.yml`.
6. **Vercel and Render.** Update `NEXT_PUBLIC_*` and `API_EMAIL_FROM` if they were set by hand.
   Project names (`mybiz-client-app`, ...) can stay; they are not shown to anyone.
7. **Run the checks**: `pnpm test` (the brand tests), `cd apps/api && uv run pytest`.

## What you cannot change later

- **The store id** (`com.businessos.mybiz`, `packages/brand/app-ids.json`). It is fixed by the
  first upload to each store. Do not upload before the name is final (go-live GL19).
- **The identity hash label** in `apps/api/app/core/identity.py`: changing it would make every
  stored hash unreadable. It is not shown to anyone.
- The listed exceptions in the embedded-name test (backup file prefix, Vercel project names,
  the old-address redirect) name their reason; none is visible to users.

## Why cookies and the palette changed in R21

Before go-live, the cookies moved from `mybiz_*` to `bos_*` (everyone signs in once more), and the
default palette is stored as `brand` instead of `mybiz` (migration 0125 allows both; the API
reads an old `mybiz` as `brand`).
