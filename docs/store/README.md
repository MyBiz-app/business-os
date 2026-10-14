# Store submission pack

Everything the Google Play and App Store forms ask for, written ahead so the owner only pastes and
uploads. Nothing here is submitted yet: iOS needs an Apple Developer account (not bought), and the
bundle ids and brand name are placeholders until the owner decides.

| File | What |
|---|---|
| [`listing.md`](listing.md) | Name, short and full description, keywords and "what's new" for the three apps, in English and Hebrew |
| [`data-safety.md`](data-safety.md) | Answers for Google Play's Data safety form and Apple's privacy labels, taken from what the code stores |
| This file | Assets, links and the owner's checklist |

## The app

| App | Folder | Id (one line to change: [`packages/brand/app-ids.json`](../../packages/brand/app-ids.json)) |
|---|---|---|
| MyBiz (clients, business and team areas in one app) | `apps/client-app` | `client` |

The ids can never change after the first store upload. Editing `app-ids.json` changes iOS and
Android, and the check in `packages/brand/test` keeps it valid. The
brand name comes from `packages/i18n/brand.json`; the app display name is in each `app.json`.

## Links the stores require

| Need | Where it lives |
|---|---|
| Privacy policy URL | `/legal/privacy` on the web app |
| Terms | `/legal/terms` |
| Support URL and email | `/contact`, and [`docs/deploy/support.md`](../deploy/support.md) |
| Account deletion (Play requires an in-app path and a web path) | In the business app: Me → close the business (owner). Clients ask the business to erase them (owner-only privacy tool); a web page for clients without a business is still to do |

## Assets

| Asset | Size | Status |
|---|---|---|
| App icon (iOS and Play) | 1024 × 1024 PNG | ✅ `apps/<app>/assets/icon.png`, drawn by `pnpm --filter @business-os/brand build:assets` |
| Android adaptive icon | foreground, background, monochrome | ✅ same folder |
| Play feature graphic | 1024 × 500 | ☐ draw from `packages/brand/assets/logo-on-dark.svg` once the name is final |
| Phone screenshots | at least 2 per app (Play 1080 × 1920 or similar; Apple 6.9″ 1320 × 2868) | ☐ capture after the name is final: run the web builds of the apps (`deploy-apps-web.yml`) and screenshot Hebrew and English, light and dark |
| Tablet screenshots | Apple requires them while `supportsTablet` is true | ☐ or set `supportsTablet` to false in the app's `app.json` to skip |

Screenshots are taken once the brand name and ids are final, so they are not redone.

## Owner's checklist

1. Choose the final brand name and the three ids (they are permanent).
2. Create the accounts: Google Play Console (one-time fee, about $25) and, for iOS, Apple
   Developer (about $99 a year).
3. Run `eas init` in each app (see [`docs/mobile-builds.md`](../mobile-builds.md)), then build with the
   `production` profile.
4. Paste the texts from `listing.md`, fill the privacy forms from `data-safety.md`, upload the assets.
5. Add testers on the internal track first.
