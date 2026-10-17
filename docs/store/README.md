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

The id is `com.businessos.mybiz` today. It can never change after the first store upload (iOS bundle
id and Android package are the same string). Editing `app-ids.json` changes both, and
`packages/brand/test` keeps it valid. The brand name comes from `packages/i18n/brand.json`; the app
display name is `name` in `apps/client-app/app.json`.

## Links the stores require

| Need | Where it lives |
|---|---|
| Privacy policy URL | `/legal/privacy` on the web app |
| Terms | `/legal/terms` |
| Support URL and email | `/contact`, and [`docs/deploy/support.md`](../deploy/support.md) |
| Account deletion (Play requires an in-app path and a web path) | In the app: Me → "Delete my account" (an owner closes the business first). Web path for Play: `/legal/privacy` explains it until a dedicated page exists |

## What is ready and what waits

| Part | State |
|---|---|
| Listing texts, Hebrew and English | Ready: [`listing.md`](listing.md) |
| Privacy labels, Data safety answers, permission texts | Ready: [`data-safety.md`](data-safety.md) |
| Notes and a test login for the store reviewers | Ready: [`review-notes.md`](review-notes.md) (the login is created at submission time) |
| Screenshot shot list and sizes | Ready: [`screenshots.md`](screenshots.md); the images wait for the final name |
| Build profiles (`eas.json`), app config (`app.json`, `app.config.js`) | Ready; Android builds are free |
| App icon and adaptive icons | Ready |
| Play feature graphic | To draw once the name is final |
| Accounts (Play Console about $25 once, Apple Developer about $99 a year) | The owner's: see the "App stores (GL19)" section of the [go-live checklist](../deploy/go-live-checklist.md) |

Nothing here has been submitted, built for the stores or paid for.

## Assets

| Asset | Size | Status |
|---|---|---|
| App icon (iOS and Play) | 1024 × 1024 PNG | Done: `apps/client-app/assets/icon.png`, drawn by `pnpm --filter @business-os/brand build:assets` |
| Android adaptive icon | foreground, background, monochrome | Done, same folder |
| Play feature graphic | 1024 × 500 | To draw from `packages/brand/assets/logo-on-dark.svg` once the name is final |
| Phone screenshots | at least 2 (Play 1080 × 1920 or similar; Apple 6.9 inch, 1320 × 2868) | See [`screenshots.md`](screenshots.md) |
| Tablet screenshots | Apple requires them while `supportsTablet` is true | Take them, or set `supportsTablet` to false in `app.json` to skip |

## Owner's checklist

The click-by-click version is in the go-live checklist, section "App stores (GL19)". In short:
choose the final name and id, create the two store accounts, run `eas init` and the production
build, paste the texts, fill the privacy forms, upload the assets, test on the internal track first.
