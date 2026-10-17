# Building the phone apps (EAS)

The one app (`apps/client-app`) is an Expo project with an
`eas.json`:

| Profile | For | Result |
|---|---|---|
| `development` | developers (dev client) | internal Android APK |
| `preview` | testers, against staging | internal Android APK |
| `production` | the stores | Android app bundle (version number auto-increments) |

## One-time setup (the owner's Expo account)

1. `npx eas-cli login`. The project is already linked (`expo.extra.eas.projectId` in `app.json`).
2. `npx eas-cli build --profile preview --platform android` builds an installable APK (free tier).
3. Production values (`EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_KEY`)
   live in the EAS environment `production` ([`deploy/production.md`](deploy/production.md), section 7).
4. iOS builds and store submission need an Apple Developer account (not bought yet). Click by click:
   [go-live checklist](deploy/go-live-checklist.md), "App stores (GL19)".

## Bundle id

`com.businessos.mybiz` (one app, same string for iOS and Android) is a placeholder until the final
brand name and domain are chosen. It cannot be changed after the first store upload. It lives only in
`packages/brand/app-ids.json`.

## Push notifications

After sign-in a phone that already allowed notifications sends its Expo push token to
`PUT /me/push-tokens`; signing out calls `DELETE`. Tokens live in `app.push_tokens` (one row per
person and device). The notification jobs send pushes through the Expo push service.
Asking for permission in a screen: call `registerPushToken({ ask: true })` from `@business-os/app-kit/lib/push`.
