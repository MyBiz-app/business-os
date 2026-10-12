# Load test, 2026-10

The three busiest journeys of the business app, run against a demo business ten times its usual size.

## What was measured

Each journey is the set of requests one screen makes when it opens (`apps/business-app/src/app/(tabs)`):

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
- Not covered: the client app's home screen, heavy parallel load (many users at once), and the AI assistant. The API runs behind a connection pool per worker (see `app/core/config.py`); a concurrency test comes with the paid-plan sizing before go-live.
