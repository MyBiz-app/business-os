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
