import assert from "node:assert/strict";
import { test } from "node:test";

import { progressOf } from "./progress.ts";

// Friday 2026-10-30, noon in Jerusalem. The week runs Sunday 25 to Saturday 31.
const now = Date.parse("2026-10-30T10:00:00Z");
const visit = (day: string, status = "checked_in", session_status = "scheduled") => ({
  starts_at: `${day}T08:00:00Z`,
  status,
  session_status,
});

test("counts this week, this month and the weeks in a row", () => {
  const history = [visit("2026-10-26"), visit("2026-10-29"), visit("2026-10-20"), visit("2026-10-13"), visit("2026-09-22")];
  assert.deepEqual(progressOf(history, "Asia/Jerusalem", now), { weekVisits: 2, monthVisits: 4, streakWeeks: 3, total: 5 });
});

test("a week without a visit yet does not break the streak, but a missed week does", () => {
  assert.equal(progressOf([visit("2026-10-21"), visit("2026-10-14")], "Asia/Jerusalem", now).streakWeeks, 2);
  assert.equal(progressOf([visit("2026-10-14")], "Asia/Jerusalem", now).streakWeeks, 0);
});

test("cancelled sessions and no-shows do not count; a past booking left unmarked does, a future one does not", () => {
  const history = [
    visit("2026-10-26", "checked_in", "cancelled"),
    visit("2026-10-27", "no_show"),
    visit("2026-10-28", "booked"),
    visit("2026-11-02", "booked"),
  ];
  assert.deepEqual(progressOf(history, "Asia/Jerusalem", now), { weekVisits: 1, monthVisits: 1, streakWeeks: 1, total: 1 });
});

test("a late-evening visit belongs to the business's local day", () => {
  // 22:30 UTC on Saturday 31 Oct is already Sunday 1 Nov, 00:30, in Jerusalem (UTC+2): a new week.
  const late = [{ starts_at: "2026-10-31T22:30:00Z", status: "checked_in", session_status: "scheduled" }];
  const monday = Date.parse("2026-11-02T12:00:00Z");
  assert.equal(progressOf(late, "Asia/Jerusalem", monday).weekVisits, 1);
  assert.equal(progressOf(late, "UTC", monday).weekVisits, 0);
});
