# End-to-end checks

`dod.py` walks the prototype's Definition of Done (spec v1 §23) through the real web app, the
client app (on Expo web) and the API, then runs axe accessibility checks in Hebrew/light and
English/dark:

register → verify email → create a business (questions → plan) → logo and colors → dashboard →
invite an employee (front desk) → service, session and member with a membership → the member
joins the branded app with a code and books → the owner sees the booking → AI answers and
proposes a booking → confirmed and executed → a platform admin sees the business and its AI usage.

## Run locally

1. `supabase start`, then `cd apps/api && uv run alembic upgrade head`
2. API with the scripted AI model: `cd apps/api && PYTHONPATH=../../e2e:. uv run uvicorn fake_ai_api:app --port 8000`
3. Web: `pnpm --filter web dev`; client app: `pnpm --filter mobile exec expo start --web --port 8081`
4. Make an existing local user a platform admin:
   `docker exec supabase_db_business-os psql -U postgres -c "insert into app.platform_staff (email, level) values ('you@example.com', 'owner')"`
5. From the repository root:
   `uv run --with playwright --with axe-playwright-python --with "psycopg[binary]" python e2e/dod.py you@example.com`

Screenshots are written to `e2e/screenshots/` (git-ignored).

`roles.py` checks custom roles through the UI (create a role, assign it, access changes, in-use role is protected). Run it the same way, without arguments, against the normal API.

`series.py` creates an open-ended weekly series, changes its time from one session on, stops it, and copies a week's one-off class to the next week.

`health.py` walks the health declaration: booking blocked without one, a "yes" waits for the studio, the studio approves on the client profile, then the member books. Run it like `roles.py`.

`client_import.py` imports a Hebrew Windows-1255 CSV: recognized columns, a column mapped by hand, preview with a duplicate and an invalid row, then the import.

`privacy.py` downloads a client's data export, then erases their personal details.

`notifications.py`: the studio books a member and cancels the class; the member sees both under Updates, with an unread badge that clears once read.

`reports.py` seeds a demo studio for a new owner and checks the reports page (breakdowns, members to reach out to, period switch).

`purchase.py`: the owner turns on online sales, a member buys a plan in the app with a test payment and edits their details, and the owner sees both on the member's profile.

`support.py <team email>`: the owner allows support access, a MyBiz team member opens the business read-only from the console, and the owner sees the visits and ends access.

`appointments.py`, `leads.py`, `messaging.py`, `billing.py`, `marketing.py`, `reviews.py`, `client_profile.py`: one flow each, run like `roles.py`.

`signup_journey.py`: the whole sign-up journey — the plan builder with its live cart, the account, the email confirmation, the simulated payment, and the dashboard with its first-steps checklist — on a phone in Hebrew and on a wide screen in English with dark mode.

`welcome.py`: a new account lands on the welcome page and explores a sample business with fictitious data.

`branches.py`: one owner with two businesses and several branches — the business menu, "My businesses", the branch picker and a new client filed under the current branch.

`upgrade.py`: a module the business doesn't have stays in the menu, locked; its preview shows what changes on the invoice, and "add to plan" turns it on.

`sales.py <owner email with data>`: the sales page for a month, its totals and the CSV export.

`console.py <team email of an owner>`: the MyBiz console — an owner builds the team (manager, employee), each level sees only its own parts, a business writes in and the inbox handles it, an owner enters a business and fixes something, extends a trial and changes a plan, and the audit log has it all.

`crawl.py <owner email with data>`: visits every page of the business app on a phone and a wide screen, in Hebrew/light and English/dark, and reports accessibility issues, console errors, overflow and screenshots.

`client_crawl.py <owner email with data>` (needs `pnpm dev:app`): a new client joins that owner's newest business, gives a name, and visits every screen of the client app on a phone in Hebrew/light and English/dark; reports accessibility issues, overflow and console errors, with screenshots.

`business_app.py <owner email with data>` (needs `pnpm --filter business-app exec expo start --web --port 8082`): the business app on a phone — today with its attention lists and the week, a session (check-in, booking someone in, a visit note), clients (filters, a new client, selling a plan, a note, a message), leads (a stage, a call, turning one into a client, a new lead), messages, numbers and settings; then the main screens in English with dark mode. If your local database listens on another port, set `E2E_DATABASE_URL`.

`staff_app.py <team email of a MyBiz owner>` (needs `pnpm --filter staff-app exec expo start --web --port 8083`, and a fresh `app.seed --demo platform`: it marks one new request done): the MyBiz team app on a phone — the numbers and what needs attention, sorting and opening a business (numbers, modules, invoices, more trial days), handling a request (take it, notes, done); then the main screens in English with dark mode.
