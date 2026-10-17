# Releases and rollback

A **release** is a tag `vMAJOR.MINOR.PATCH` (for example `v1.0.0`) on `main`. Staging keeps
following `main`; production moves only when a tag is approved. Nothing here deploys by itself
until production exists ([production.md](production.md)).

## Cutting a release

1. `main` is green (CI) and the nightly end-to-end run has no open issue.
2. `git tag v1.0.0 && git push origin v1.0.0` (from an up to date `main`).
3. Two workflows start from the tag:
   - [`release.yml`](../../.github/workflows/release.yml) writes the GitHub Release with notes
     generated from the merged pull requests. It deploys nothing.
   - [`deploy-web-production.yml`](../../.github/workflows/deploy-web-production.yml) waits for
     your approval in the `production` environment, records the tag and commit in the run summary,
     deploys the website, starts the API deploy when `RENDER_DEPLOY_HOOK_URL` is set, then checks
     both addresses. If the website is not healthy within 3 minutes it goes back to the previous
     deployment by itself; the API goes back too when `RENDER_API_KEY` is set.
4. Open the run, check the summary, open the site.

Patch releases (`v1.0.1`) are a new tag on `main` after the fix is merged. Never move or delete a
tag that was released.

## Rolling back

Run **Actions, Roll back, Run workflow**: choose the environment (`staging` or `production`) and
what to roll back (`both`, `api` or `web`). Leave the two optional fields empty to return to the
previous version, or fill them to pick an exact one (a Vercel deployment address, a Render deploy
id). Production asks for approval first. After the rollback the workflow checks the health
addresses again.

Setup in each GitHub environment (`staging`, `production`): secrets `VERCEL_TOKEN` and
`RENDER_API_KEY` (Render, Account Settings, API Keys; free), variables `RENDER_SERVICE_ID` (the
`srv-...` id from the service URL), `HEALTH_API_URL` and `HEALTH_WEB_URL`. For production also
`PRODUCTION_VERCEL_ORG_ID` and `PRODUCTION_VERCEL_PROJECT_ID`, `PRODUCTION_WEB_URL` and
`PRODUCTION_API_URL` as repository variables (used by the post-deploy check).

By hand, without the workflow: Render, the service, Events, redeploy the previous successful
deploy; Vercel, Deployments, the previous production deployment, Promote to Production.

## Rollback and the database (expand first, contract later)

A rollback puts the previous code back; the database stays as it is. That is safe only if the
previous version can run on the newer schema. The rule for every migration:

1. **Expand** in release N: add tables, columns (nullable or with a default) and indexes. The old
   code ignores them. Never drop, rename or retype in the same release that stops using something.
2. **Contract** in release N+1 or later: drop or rename only what no running version uses any
   more, after at least one release went by.
3. A migration from 0117 on that drops or renames a table or column, or changes a column type,
   must carry a line `# contract: <why the previous version still works>`. The test
   `apps/api/tests/test_migration_contract.py` fails the pull request without it.

If a release must be undone and its migration cannot be left in place, restore from a backup
instead ([restore-runbook.md](restore-runbook.md)); that is a decision for the owner.

## Practising it once (done when)

After the single final deploy to staging: run **Roll back** with environment `staging` and
component `both`, check the health step is green and the site and API answer, then deploy `main`
again. Write the date and result in the table below.

| Date | Environment | What | Result |
|---|---|---|---|
| (not practised yet) | | | |

## Nightly end-to-end

[`e2e.yml`](../../.github/workflows/e2e.yml) also runs every night on `main` against a local stack
built in the runner (not against staging, so it cannot disturb demo data). A failed nightly run
opens one issue titled "Nightly end-to-end run failed" and comments on it while it stays open.
