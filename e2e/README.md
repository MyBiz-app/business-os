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
