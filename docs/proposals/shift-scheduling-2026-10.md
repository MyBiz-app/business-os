# Shift scheduling for multi-branch businesses (2026-10-10)

Part 2 of the owner's workspace list, "employee scheduling". Builds on the shift board from
PR #134 (`app.shifts`, `GET/POST/PATCH/DELETE /shifts`, copy week). Slices: **1 data and API**,
**2 the board** (day / week / month / custom, by person and by branch), **3 team and demo**
(home branch in the team screens, demo data, roles view is a separate thread).

## What the owner asked for

1. A comfortable interface for planning who works when.
2. Planning rhythm per branch: weekly by default; daily, monthly or custom as options.
3. Every employee has a **home branch** where they normally work, but the owner can place
   them one time in another branch (Hadar always works in Holon, tomorrow she covers Hod
   HaSharon).
4. See several branches side by side for one day ("tomorrow in Ashdod and Tel Aviv: who is on,
   and when").

## Model

| What | Where | Notes |
|---|---|---|
| Home branch | `tenant_members.home_location_id` | Optional. Informational: it does not limit where a shift can be placed and never changes what the person can see (`location_ids` still does that). |
| Planning rhythm | `locations.planning_cadence` (`daily` / `weekly` / `monthly` / `custom`, default `weekly`) and `locations.planning_days` (only for `custom`, 1-42) | Decides the length of the window the board opens on for that branch. |
| Cover shift | derived, not stored | A shift is a **cover** when the person has a home branch and the shift is at another one. Returned as `is_cover` plus the home branch name. |

A one-time placement therefore needs no new concept: it is an ordinary shift at another
branch, marked as cover on the board. The existing overlap check (one person, no two
overlapping shifts, in any branch) already prevents double-booking someone across branches.

## API

- `PUT /staff/{user_id}/home-branch` `{location_id | null}` (needs `staff.manage`).
- `GET /shifts/planning` lists each visible branch's rhythm; `PUT /locations/{id}/planning`
  sets it (needs `catalog.write`).
- `Shift` gains `home_location_id`, `home_location_name`, `is_cover`; `Member` gains
  `home_location_id`.

## Board (slice 2)

- **Window**: day / week / month / custom (N days), opened on the branch's rhythm; previous and
  next step by the window, with "today", and day-by-day arrows in the day and week views.
- **View**: *by person* (rows are people, as today) and *by branch* (one column per selected
  branch, each lists who is on and when). Day view: any number of branches; week: up to 3;
  month: one.
- Day and week "by branch" (two or more branches) use the shared calendar `TimeGrid`: one lane per branch, each shift a block placed by its hours; a block opens the shift editor (`?edit=<id>`). The month view and the single-branch case keep the plain roster list.
- Branch chips choose which branches are shown. Cover shifts are marked.
- The shared multi-branch calendar grid and the owner's default-view preference belong to the
  calendar thread; the board reuses them when they land.

## Out of scope

Shift swaps and approvals, labor-law checks, payroll hours, push notifications to staff.
