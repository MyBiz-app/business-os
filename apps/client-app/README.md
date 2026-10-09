# MyBiz mobile (client app)

The app end customers use: sign in with an emailed 6-digit code, join a business with its join
code (or QR), browse the schedule, book, join waitlists and cancel.

## Run against your local stack

1. Start the local stack from the repository root (`supabase start`, the API on port 8000).
2. `pnpm --filter client-app start`, then scan the QR code with Expo Go (same Wi-Fi as the computer).

The app reaches the API (`:8000`) and Supabase (`:54321`) on the computer that runs the Expo
dev server. Sign-in codes arrive in the local mailbox at http://127.0.0.1:54324.

To try it in a browser instead: `pnpm --filter client-app exec expo start --web`.

## Run against staging

Create `apps/client-app/.env.local` (not committed) with the staging values:

```
EXPO_PUBLIC_API_URL=https://business-os-api-staging.onrender.com
EXPO_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
EXPO_PUBLIC_SUPABASE_KEY=<the project's publishable / anon key>
```

These are public client values (the same ones the website uses), not secrets.
The staging Supabase project's "Magic link" and "Confirm signup" email templates must include
`{{ .Token }}` so emails contain the code (see `supabase/templates/`).

## Publish as a web app (staging)

The same app runs in a phone's browser, so people can try it without installing anything.
It is a static site (`expo export -p web`), deployed by a second Vercel project:

1. Vercel → *Add New → Project* → this repository, **Root Directory** `apps/client-app`
   (build settings come from [`vercel.json`](vercel.json)).
2. Environment variables: `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_SUPABASE_URL`,
   `EXPO_PUBLIC_SUPABASE_KEY` (the staging values above) and `ENABLE_EXPERIMENTAL_COREPACK=1`.
3. Deploy, then allow the app's address on the API: Render → service → Environment →
   `API_CORS_ORIGINS` = `["https://<the app's vercel address>"]`.
