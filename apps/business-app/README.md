# MyBiz for business owners and staff (Expo)

The day on the go: today's schedule, check-in, clients and the key numbers. The business web
app (`apps/web`) stays the full system; this app is what you open between clients.

Sign in with the email that was invited to the business team. Everything follows the same
permissions as the web app, and the API checks them again on every request.

```bash
pnpm --filter business-app exec expo start          # phone (Expo Go)
pnpm --filter business-app exec expo start --web    # browser, port 8082
```

It talks to the API and Supabase on the computer running Expo (same Wi-Fi). Other environments
set `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_SUPABASE_URL` and `EXPO_PUBLIC_SUPABASE_KEY`.
