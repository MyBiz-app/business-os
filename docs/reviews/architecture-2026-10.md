# Architecture review after phase 4 (#40)

_2026-10-05_ · Whole-system review: database security, API surface, principles, shared
packages, performance, tests. Fixed items landed with migration 0043; the rest are tracked as
issues.

## Summary

Tenant isolation holds. Every router endpoint has a context dependency, and RLS is
membership-based (the tenant header alone grants nothing). Client data is scoped by
`current_client_id()`. Public endpoints are rate-limited in the database. No IDOR was found.
Money is integer minor units everywhere, and there is no `timestamp without time zone`.
Physical CSS (left/right) was not found in the web app.

## Fixed in this round

| Finding | Fix |
|---|---|
| `default_location_id(tenant, client)` and `sync_extra_locations_for(tenant)` are SECURITY DEFINER and callable by the API role with any business id: they could read another business's branches or rewrite its extra-branch quantity | API role loses EXECUTE. The triggers that use them run as the owner. The API uses the new `sync_my_extra_locations()`, which reads the business from the request. |
| The API role could UPDATE every column of `tenants`, including `trial_ends_at`, `id`, `created_at` | Column-level UPDATE grant on settings columns only; the trial changes only through the console rule |
| `current_tenant_id()`, `current_user_id()`, `is_member()` executable by PUBLIC | Revoked; granted to the API role only |
| Hot queries without an index: payments per client/plan, a coach's sessions, bookings per session, pending actions, messages, usage across businesses, several join keys | 14 indexes (migration 0043) |
| AI usage was lost when the model failed midway (the request rolled back the usage of calls already made) | The partial turn rolls back to a savepoint; the usage is recorded and committed before the error is returned |
| A tool call missing a required input crashed the request (500) | Returned to the model as a tool error |
| Notification emails emitted no usage event | One `messages` usage event per business per batch, `channel: email` |
| Hard-coded labels: language names in the business and team apps, "Email" on the receipt | Translations |

## Follow-ups

| Finding | Where | Tracking |
|---|---|---|
| Branch assignment of team members (`location_ids`) is stored but does not restrict anything | `api/deps.py` `set_branch` | [#64](https://github.com/MyBiz-app/business-os/issues/64) (owner's decision) |
| N+1 queries in loops: series update and closing a day, `/me/businesses`, staff hours insert | `api/schedule.py`, `api/businesses.py`, `api/appointments.py` | [#63](https://github.com/MyBiz-app/business-os/issues/63) |
| Sign-in screen identical in three apps; app root and preferences card nearly identical | `apps/*/src/app` | [#63](https://github.com/MyBiz-app/business-os/issues/63) |
| Money formatting duplicated (web and app-kit) and `/100` inline in three places; assumes two decimals | `apps/web/src/lib/money.ts`, `packages/app-kit/src/lib/money.ts` | [#63](https://github.com/MyBiz-app/business-os/issues/63) |
| Share image is English-only (needs a Hebrew font for the image renderer) | `apps/web/src/app/(marketing)/opengraph-image.tsx` | [#63](https://github.com/MyBiz-app/business-os/issues/63) |
| Fitness as the default industry in the start wizard and contact form | `start-wizard.tsx`, `contact-form.tsx` | [#63](https://github.com/MyBiz-app/business-os/issues/63) |
| Tests missing for `/me/businesses` with several businesses, closed days delete, a business's invoices in the console | `apps/api/tests` | [#63](https://github.com/MyBiz-app/business-os/issues/63) |
| RLS is enabled but not FORCED: safe because the table owner is never the API role. Forcing it changes nothing while the owner bypasses RLS | All tables | Noted; revisit if the API ever connects as the owner |
