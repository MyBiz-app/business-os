# Restore runbook

How to get the data back when something goes wrong. Read it before you need it, and run the
drill (last section) once the production database exists.

**Status:** staging runs on the Supabase free plan, which has **no usable backups and no
point-in-time restore**. Everything below the "Production" heading assumes the Pro plan with daily
backups and the PITR add-on (go-live item B1/B4 in [the go-live review](../reviews/go-live-readiness-2026-10.md)).
Until then, the only safety net is the demo seed ([`seed-staging.yml`](../../.github/workflows/seed-staging.yml)).

## What holds data, and how it comes back

| Data | Where | Recovery |
|---|---|---|
| Businesses, clients, bookings, money, audit log | Supabase Postgres | Point-in-time restore or a daily backup (below) |
| Sign-in accounts | Supabase Auth (same project) | Restored together with the database |
| Uploaded files (documents, logos) | Supabase Storage when `API_STORAGE_PROVIDER=supabase`; otherwise Postgres rows | Storage objects are **not** in the database backup. Enable bucket versioning/export before go-live, or accept that files since the last export are lost |
| Secrets and settings | Render, Vercel and GitHub environments | Not in any backup. Keep the list of names in [`staging.md`](staging.md); values live in the owner's password manager |
| Code | GitHub | `git clone`; redeploy from `main` |

## Decide first

1. **What broke?** A bad migration or bug that corrupted rows → restore to a time just before it
   (PITR). Project deleted or lost → restore the latest daily backup. A single business asked for
   its data → use the account export, not a restore.
2. **Stop the writes.** In Render, suspend the API service (or set it to maintenance) so nothing
   new is written while you restore. Keep the web site up; it shows the API-unavailable state.
3. **Write down the time.** The restore point you choose is the data you will lose after it.

## Production: restore a project (Supabase Pro)

1. Supabase dashboard → the production project → **Database → Backups**.
2. Pick **Point in time** (choose the minute before the incident, in UTC) or a **daily backup**.
3. Start the restore. The project is unavailable until it finishes; the dashboard shows progress.
4. When it is back, check the migration head matches the code:
   `alembic current` (run the [`migrate-staging.yml`](../../.github/workflows/migrate-staging.yml)
   pattern against the production URL). If the restore point is older than the deployed code,
   the API's start-up `alembic upgrade head` brings the schema forward; if a migration caused the
   incident, redeploy the previous release first.
5. Resume the Render API service. Check `GET /health/ready` returns 200.
6. Smoke test: sign in, open the schedule, open one client, book a slot, open a document.
7. Tell affected businesses what time the data is current to (see [support](support.md)).

## Restore into a scratch project (safe rehearsal, or to recover a few rows)

Use this to inspect old data without touching production.

1. Create a scratch Supabase project, or use a Supabase branch.
2. Restore the backup into it (dashboard restore to a new project, or `pg_restore` of a dump).
3. Connect with `psql` using the session-pooler URL, find the rows, and copy only those back with
   `INSERT … SELECT` through a reviewed script. Never copy `tenant_id`-scoped rows without
   checking the tenant.
4. Delete the scratch project when done (it holds real personal data).

## Manual dump (extra safety before risky work)

Before a risky migration, take a dump from the session pooler URL (never commit it):

```
pg_dump --format=custom --no-owner "$DATABASE_URL" -f mybiz-$(date -u +%Y%m%dT%H%MZ).dump
```

Store it encrypted, outside the repository, and delete it after the change is verified. Restore
with `pg_restore --clean --if-exists --no-owner -d "$TARGET_URL" file.dump` into a scratch database
first.

## Bad migration

Migrations are forward-only in practice. If one fails in the container start-up, Render keeps the
previous deploy running: fix forward with a new migration, or roll back the release in Render and
restore only if data was damaged. Migration numbers are linear; check for a duplicate head
(`alembic heads` must print one line).

## After any restore

- Re-run the nightly/hourly jobs once ([`jobs-staging.yml`](../../.github/workflows/jobs-staging.yml)
  pattern): reminders are idempotent but check for duplicates.
- Sessions or bookings made after the restore point are gone: ask the owners of affected
  businesses to re-check their schedule for that window.
- Write an incident note (see [on-call](on-call.md)).

## The restore drill

Do this once after production exists, then every quarter, and after any change of hosting.

1. Note the start time. Restore last night's backup into a scratch project.
2. Point a local API (`API_DATABASE_URL`) at it and run the smoke test above.
3. Record in the table below: the date, backup used, how long the restore took, what was missing.
4. Delete the scratch project.

| Date | Backup / PITR time | Restore took | Result | Who |
|---|---|---|---|---|
| _not yet run_ | | | | |

Target: a business is back within **2 hours** of the decision to restore, losing at most the last
**5 minutes** (PITR) or **24 hours** (daily backup only). Adjust once the drill shows real numbers.
