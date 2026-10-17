# Load test, 2026-10

The three busiest journeys of the business area of the app, run against a demo business ten times its usual size.

## What was measured

Each journey is the set of requests one screen makes when it opens (`apps/client-app/src/app/(business)`):

| Journey | Requests |
|---|---|
| Today | sessions (7 days), attention lists, resources, services, billing usage |
| Clients | client list, search, "no plan" filter, "absent 14 days" filter |
| Numbers | six metrics with the previous period, breakdown by service, members at risk, daily revenue series |

The data is the standard demo studio (170 clients, 3 months of history) against the same studio with 1,700 clients, which also gives about 2x the bookings and 10x the payments and plans. The class timetable is the same size, because a business does not run ten times as many classes because it has ten times as many clients. 15 timed runs per journey, in-process (no network), requests one after another, so screens that fetch in parallel are a little faster in real life.

Run it with `LOAD_TEST=1 uv run pytest tests/load -s` in `apps/api`. It also runs in CI (job "Load test") and writes its table into the job summary. The CI budget is p95 below 2 seconds per whole journey at 10x: it catches a missing index or a query per client, not a slow runner.

## Result

Seconds for the whole journey, on a laptop-class container. Before is the first run; after is with the fix below.

| Journey | 1x p95 (before) | 10x p95 (before) | 1x p95 (after) | 10x p95 (after) |
|---|---|---|---|---|
| Today | 1.41 | 1.71 | 0.98 | 0.53 |
| Clients | 0.32 | 0.65 | 0.31 | 0.63 |
| Numbers | 0.96 | 2.24 | 0.56 | 1.08 |

(The 1x run goes first, and its "Today" figure is probably inflated by a cold database cache: it is slower than the 10x run right after it.)

## Finding and fix

`members_at_risk` (the "who is drifting away" list on Today and Numbers) looked up each client's last visit and plan end with one subquery per client: about 1,200 index lookups at 10x, and it ran twice on Numbers. It now reads bookings and plans once each and joins them. Same result (the existing report and attention tests pass), about half the time at 10x, and it no longer grows with the number of clients' lookups.

## What is still the slowest, and what to do about it

- **Numbers, about 1.1 s at 10x.** The six metrics are computed one by one, each for two periods. If this screen becomes slow with real data, compute the metrics in one pass or cache the previous period (it never changes).
- **Clients, about 0.6 s at 10x.** Search uses a `LIKE '%text%'` scan; a trigram index would help from a few thousand clients.
- Not covered: the client app's home screen and the AI assistant. Many users at once is covered below.

## Parallel load with k6 (go-live GL18)

The test above runs one request at a time. This one has many people at once: k6 scripts in `apps/api/tests/load/k6/` run 50, 100 or 200 virtual people, each looping through the five busiest journeys of the business app: the **timetable** (a week of classes), a **booking** (book a client into a class, then cancel), the **shifts** board, a **client card** (client and their bookings) and the **dashboard** (attention lists, resources, services, usage, metrics).

### Run it

Free, on a laptop or a container; never against production. Needs `k6` (free, a single binary) and a local Postgres.

```
cd apps/api
# 1. a migrated database with one demo business of 8,500 clients (50x the demo), a signing key and a token
uv run python -m tests.load.local_stack --clients 8500 > stack.json      # keeps serving the key set
# 2. the API on the same database (second terminal; the last line of stack.json holds database_url, tenant_id, token)
API_DATABASE_URL=... API_JWKS_URL=http://127.0.0.1:54399/jwks.json uv run uvicorn app.main:app --workers 2
# 3. the load
k6 run -e TENANT_ID=... -e TOKEN=... -e VUS=100 -e DURATION=60s tests/load/k6/journeys.js
```

Against staging, at night: the same script with `-e BASE_URL=https://<staging api> -e TENANT_ID=<demo business> -e TOKEN=<a signed-in owner's token>`, and `VUS=50` first. Local development has the rate limits off; on staging they are on, so a one-business test hits the business ceiling (below) and the address limit, which is what they are for: raise `API_TENANT_RATE_LIMIT_PER_MINUTE` and set `API_RATE_LIMITS=false` for the night, then put them back.

### Result (this container: 4 cores shared by k6, the API and Postgres)

Requests per second the API sustained, the share of requests that failed, and the p95 of the slowest journey, with 2 API workers (45 s at full load):

| Business | 50 people | 100 people | 200 people |
|---|---|---|---|
| 300 clients (typical) | 24 req/s, 0.6% failed, 9 s | 23 req/s, 2.5% failed, 33 s | 19 req/s, 10% failed, 57 s |
| 8,500 clients (50x) | 10 req/s, 0% failed, 35 s | 11 req/s, 3% failed, 65 s | 9 req/s, 19% failed, 60 s |

What it says:

- **The ceiling is CPU, and it is flat.** Throughput stops growing at about 50 people; more people only queue, so the wait grows in proportion. 4 workers instead of 2 gave 23 and 25 req/s instead of 24 and 23 (300 clients, 50 and 100 people): no gain on 4 shared cores, so the default of 2 workers stays. The connection pool (5 + 10 per worker) was left as it is: nothing in these runs pointed at it.
- **Two requests cost most.** On the 8,500-client business, with one person and nobody else, the timetable (`GET /sessions`, one week) takes about 0.8 s and the dashboard's attention lists (`GET /attention`) about 1.2 s, of which about 0.9 s is the members-at-risk query; the client list (`GET /clients`) takes 0.9 s, of which 0.5 s is the row-level-security count. Fixing these is the cheapest way to raise the ceiling (the client list is GL17's pagination and trigram work). Not done in this slice.
- **The failures at 200 people are the wait**: the warnings k6 printed were request timeouts (60 s), not errors from the API.

### How many businesses one instance holds

A person who is working in the app opens a screen about once a minute and a screen is 1 to 5 requests, so a busy person is about 0.2 requests per second, and a business with five people working at the same moment is about 1 request per second. This container held 24 requests per second of this (deliberately heavy) mix on four cores.

**Estimate, to be confirmed on staging: one Render Starter instance (0.5 CPU) holds about 15 active businesses**, counting that a fifth of the businesses are at their peak at the same time. The step up is the Standard plan (1 CPU), about 30 businesses, or removing the two slow requests above, which roughly doubles every number here. It is an estimate because Starter's CPU was not available to measure; the staging run at night (command above, `VUS=20` and then `50`) gives the real figure and goes into this table.

| Plan | Instances | Active businesses (estimate) |
|---|---|---|
| Starter (0.5 CPU, $7) | 1 | about 15 |
| Standard (1 CPU) | 1 | about 30 |
| Starter, two instances with a shared rate-limit store | 2 | about 30 |

### The per-business ceiling

One business cannot use up the API for the others: after sign-in is checked and the person is known to belong to the business, each business is counted in a one-minute window (staff and clients of the app together, through the same store as the address limits). The default is 600 requests a minute (`API_TENANT_RATE_LIMIT_PER_MINUTE`, 0 turns it off); over it the answer is `429` with `{"detail": "tenant_rate_limited"}` and a `Retry-After` header. The header `X-Tenant-Id` alone is never counted: someone who is not a member gets 403 before anything is counted, so they cannot spend another business's allowance. The MyBiz team and support visits are not counted. 600 is about 10 requests a second for one business: more than five busy people reach. `tests/load/k6/quota.js` checks it against a running API (rate limits on).

### Shared counts for more than one instance

With two or more API instances the counts (address and business) must be shared, or each instance allows its own full limit. The shared store is Redis: set `API_RATE_LIMIT_REDIS_URL` (steps in [deploy/staging.md](../deploy/staging.md)). Not set anywhere yet, so the counts stay per process, which is right for one instance.
