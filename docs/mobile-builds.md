# Building the phone apps (EAS)

Each app (`apps/client-app`, `apps/business-app`, `apps/staff-app`) is its own Expo project with an
`eas.json`:

| Profile | For | Result |
|---|---|---|
| `development` | developers (dev client) | internal Android APK |
| `preview` | testers, against staging | internal Android APK |
| `production` | the stores | Android app bundle (version number auto-increments) |

## One-time setup (the owner's Expo account)

1. `npx eas-cli login`, then in each app folder `npx eas-cli init`. This writes
   `expo.extra.eas.projectId` into that app's `app.json`. Push registration stays off until it exists.
2. `npx eas-cli build --profile preview --platform android` builds an installable APK (free tier).
3. iOS builds and store submission need an Apple Developer account (not bought yet).

## Bundle ids

`com.businessos.mybiz`, `.mybiz.business` and `.mybiz.team` are placeholders. They cannot be changed
after the first store upload, so the owner picks the final ones (and the brand name) first.

## Push notifications

After sign-in a phone that already allowed notifications sends its Expo push token to
`PUT /me/push-tokens`; signing out calls `DELETE`. Tokens live in `app.push_tokens` (one row per
person and device). Sending pushes (Expo push service, from the notification jobs) is not built yet.
Asking for permission in a screen: call `registerPushToken({ ask: true })` from `@business-os/app-kit/lib/push`.
