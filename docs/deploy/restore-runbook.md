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
| Uploaded files (documents, logos) | Supabase Storage when `API_STORAGE_PROVIDER=supabase`; otherwise Postgres rows | Storage objects are **not** in the database backup. The [second backup](#the-second-backup-cloudflare-r2) copies the bucket to R2 every day |
| Independent copy of both | Cloudflare R2 (encrypted dumps, 30 days; files) | Used when Supabase itself is lost: [restore from the second backup](#restore-from-the-second-backup) |
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

## The second backup (Cloudflare R2)

A copy that does not depend on Supabase, so losing the project, the account or the backups
themselves is survivable. Built in GL15, **off** until the steps below are done. Free (R2 free tier:
10 GB, no egress fees).

What runs ([`backup-offsite.yml`](../../.github/workflows/backup-offsite.yml), every day 01:40 UTC):

1. `scripts/backup/backup-db.sh`: `pg_dump` piped through `age` (encrypted with the public key, so
   no unencrypted dump ever touches a disk), uploaded as `db/mybiz-<UTC time>.dump.age`; dumps older
   than 30 days are deleted.
2. `scripts/backup/copy-files.sh`: the Supabase Storage bucket is synced to `files/` in the same R2
   bucket (only when `FILES_S3_ENDPOINT` is set). Deletions are not mirrored; set an R2 lifecycle rule
   to expire `files/` objects you no longer want.
3. A failed run opens one issue "Second backup failed".

### Switching it on (owner task A2, about 15 minutes)

1. Cloudflare (free account, two-step sign-in on) → R2 → create bucket `mybiz-backups`. Settings →
   S3 API: copy the endpoint `https://<account-id>.r2.cloudflarestorage.com`.
2. R2 → Manage API tokens → create a token with **Object Read & Write** on that bucket only. Copy the
   key id and secret.
3. On your own machine make the age key pair (install `age`, then `age-keygen -o mybiz-backup.key`).
   The line `Public key: age1...` is safe to share. **Keep `mybiz-backup.key` in your password manager
   and on a second device; whoever holds it can read every backup and nobody can recover it for you.**
4. GitHub → repository Settings → Environments → new environment `backup`. Secrets:
   `BACKUP_DATABASE_URL` (Supabase session pooler string), `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`.
   For files also `FILES_S3_ACCESS_KEY_ID`, `FILES_S3_SECRET_ACCESS_KEY` (Supabase → Storage → S3
   connection → new access key).
5. Repository Settings → Secrets and variables → Actions → Variables: `BACKUP_AGE_RECIPIENT` (the
   public key), `R2_ENDPOINT`, `R2_BUCKET`; for files also `FILES_S3_ENDPOINT`
   (`https://<project-ref>.storage.supabase.co/storage/v1/s3`) and `FILES_BUCKET`.
6. Set the variable `OFFSITE_BACKUP_ENABLED` to `true`. Run the workflow once by hand (Actions →
   Second backup → Run workflow) and check the object appears in R2.
7. Run the restore drill (below) the same day.

## Restore from the second backup

Use when Supabase (or its backups) are not available.

1. Create an empty Postgres (a new Supabase project, or any Postgres 15 or newer).
2. On a machine with `age`, `aws`, `psql` and `pg_restore`:

```
export TARGET_DATABASE_URL="postgresql://..."      # the EMPTY new database
export AGE_IDENTITY_FILE=mybiz-backup.key
export R2_ENDPOINT=... R2_BUCKET=... AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=...
scripts/backup/restore-drill.sh
```

   It takes the newest dump, decrypts it, restores it, and prints the table count, the migration
   head and the elapsed time. To use an older dump, download it with `aws s3 cp` and set
   `LOCAL_DUMP=<file>`. The script refuses a database that already has tables.
3. Files: copy `files/` from R2 back into the Storage bucket with `aws s3 sync` (same keys and
   endpoint pattern as `copy-files.sh`, reversed).
4. Continue at "Production: restore a project", step 4 (migration head, resume the API, smoke test).

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

1. Note the start time. Restore last night's backup into a scratch database: run the **Restore
   drill** workflow (Actions; it needs the secret `BACKUP_AGE_IDENTITY` = the contents of your private
   key file, added just for the drill and deleted after), or run `scripts/backup/restore-drill.sh`
   yourself. A reminder issue opens on the first day of every quarter.
2. Point a local API (`API_DATABASE_URL`) at it and run the smoke test above.
3. Record in the table below: the date, backup used, how long the restore took, what was missing.
4. Delete the scratch project.

| Date | Backup / PITR time | Restore took | Result | Who |
|---|---|---|---|---|
| 2026-10-17 | Synthetic: 50,000-row test database, encrypted and restored with the real scripts on a local Postgres 16 | 0 s (about 1 MB; proves the scripts, not a real timing) | Passed: decrypt, restore, migration head and table count checks; a non-empty target is refused | Claude (GL15) |
| _first real drill_ | _after A2: latest R2 dump_ | | | owner |

Target: a business is back within **2 hours** of the decision to restore, losing at most the last
**5 minutes** (PITR) or **24 hours** (daily backup only). Adjust once the drill shows real numbers.
