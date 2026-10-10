# Schedule board: multi-branch day, week and month (2026-10)

Owner ask (Part 2 of the CRM upgrade): a schedule that is easy to read and to compare across branches.

## What changes

- **Branches as columns.** Day view: every picked branch is a block of its own under the day header,
  with a named, colored branch header on top of each block (up to 6 branches). Week view: each day
  holds up to 3 branch columns. Month view: one branch. A day is still one column (strip) of time.
- **The number on the side.** In the old multi-branch day view the narrow strip at the grid's edge
  showed how many team members were on shift, summed over all branches, with no label. Now every
  branch column has its own strip, labeled with a people icon, and the legend says what it is.
- **Navigation.** Day: `week back / day back / Today / day forward / week forward`. Week: week
  back/forward. Month: month back/forward. All with text labels, plus a date picker to jump anywhere.
- **Default view per business.** The owner (permission `business.settings`) saves "this view as the
  default": range (`schedule_default_view`) and up to 3 branches (`schedule_default_branches`) on
  `app.tenants`. With no branches saved, the menu's branch applies as before. Explicit links
  (`?view=`, `?branches=`) always win.

## Reuse (the staff shift board)

The grid lives in `apps/web/src/components/calendar-board/`:

- `TimeGrid` takes `days` and optional `lanes` (`{id, name, color}`); events and shifts carry the
  `lane` they belong to. A lane is any parallel column group: a branch today, a court or a staff
  member tomorrow.
- `MonthGrid` shows a month of events as chips per day.
- `layout.ts`: pure helpers for the limits per range.

## Decisions

- Limits: day 6 branches, week 3, month 1 (readability, not data).
- Default is stored as two columns on the business, not per user: the owner sets the house view.
