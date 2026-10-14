# MyBiz for the MyBiz team (Expo)

The console in your pocket. The full console lives in the web app (`/platform`); this app is for
answering a request from the bus:

- **Home**: the platform's numbers, this month's billing, open requests and new businesses.
- **Businesses**: search and sort; a business card with its owner, numbers, modules, invoices and
  (with billing rights) more trial days.
- **Inbox**: a request card to call or write back, take it, move its status and keep notes.

Sign in with the email that is on the MyBiz team. Tabs follow your level and permissions, and
the API checks them again on every request.

```bash
pnpm --filter staff-app exec expo start          # phone (Expo Go)
pnpm --filter staff-app exec expo start --web    # browser, port 8083
```

## Publishing an over-the-air update

`eas update` bundles `EXPO_PUBLIC_*` at publish time and ignores `eas.json` build env. Publish with the **Publish Expo app updates (EAS Update)** GitHub workflow (needs the `EXPO_TOKEN` secret), or export `EXPO_PUBLIC_API_URL`, `EXPO_PUBLIC_SUPABASE_URL` and `EXPO_PUBLIC_SUPABASE_KEY` (see the workflow file) before running `eas update --branch preview --environment preview`. Without them the app calls `http://<host>:8000` and sign-in fails with "(0)".
