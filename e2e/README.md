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
   `docker exec supabase_db_business-os psql -U postgres -c "insert into app.platform_admins select id from app.users where email = 'you@example.com'"`
5. From the repository root:
   `uv run --with playwright --with axe-playwright-python --with "psycopg[binary]" python e2e/dod.py you@example.com`

Screenshots are written to `e2e/screenshots/` (git-ignored).

`roles.py` checks custom roles through the UI (create a role, assign it, access changes, in-use role is protected). Run it the same way, without arguments, against the normal API.

`series.py` creates an open-ended weekly series and stops it from one of its sessions.

`health.py` walks the health declaration: booking blocked without one, a "yes" waits for the studio, the studio approves on the client profile, then the member books. Run it like `roles.py`.

`client_import.py` imports a Hebrew Windows-1255 CSV: recognized columns, a column mapped by hand, preview with a duplicate and an invalid row, then the import.

`privacy.py` downloads a client's data export, then erases their personal details.

`notifications.py`: the studio books a member and cancels the class; the member sees both under Updates, with an unread badge that clears once read.
