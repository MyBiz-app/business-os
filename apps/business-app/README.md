# MyBiz for business owners and staff (Expo)

The day on the go, from the phone. The business web app (`apps/web`) stays the full system; this
app is what you open between clients:

- **Today**: the week's days, each day's sessions, and what needs attention (plans ending,
  clients drifting away, leads to call back, health declarations).
- **A session**: check-in and no-show, booking a client in, cancelling a booking, a visit note.
- **Clients**: search and filters, a new client, and the client card: contact, plans and selling
  one (simulated payment), what's coming up, recent visits, notes and a WhatsApp message.
- **Leads** (CRM module): by stage, a lead card (call, move the stage, log a call, turn into a
  client) and a new lead. **Messages** (WhatsApp module): what was sent.
- **Numbers** and **Me** (profile, language, theme, branch, business).

Screens are built from the shared kit (`packages/app-kit`: `components/ui` and `components/rows`).

Sign in with the email that was invited to the business team. Everything follows the same
permissions as the web app, and the API checks them again on every request.

```bash
pnpm --filter business-app exec expo start          # phone (Expo Go)
pnpm --filter business-app exec expo start --web    # browser, port 8082
```

It talks to the API and Supabase on the computer running Expo (same Wi-Fi). Other environments
set `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_SUPABASE_URL` and `EXPO_PUBLIC_SUPABASE_KEY`.
