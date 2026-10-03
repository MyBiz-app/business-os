# MyBiz mobile (client app)

The app end customers use: sign in with an emailed 6-digit code, join a business with its join
code (or QR), browse the schedule, book, join waitlists and cancel.

## Run against your local stack

1. Start the local stack from the repository root (`supabase start`, the API on port 8000).
2. `pnpm --filter mobile start`, then scan the QR code with Expo Go (same Wi-Fi as the computer).

The app reaches the API (`:8000`) and Supabase (`:54321`) on the computer that runs the Expo
dev server. Sign-in codes arrive in the local mailbox at http://127.0.0.1:54324.

To try it in a browser instead: `pnpm --filter mobile exec expo start --web`.

## Run against staging

Create `apps/mobile/.env.local` (not committed) with the staging values:

```
EXPO_PUBLIC_API_URL=https://business-os-api-staging.onrender.com
EXPO_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
EXPO_PUBLIC_SUPABASE_KEY=<the project's publishable / anon key>
```

These are public client values (the same ones the website uses), not secrets.
The staging Supabase project's "Magic link" and "Confirm signup" email templates must include
`{{ .Token }}` so emails contain the code (see `supabase/templates/`).
