import assert from "node:assert/strict";
import { test } from "node:test";

import { calendarLink, groupByRecency, isLateCancel, knownCards, lastVisit, nextBooking } from "./client-home.ts";

const booking = (starts_at: string, status = "booked", session_status = "scheduled") => ({ starts_at, status, session_status });
const now = Date.parse("2026-10-14T10:00:00Z");

test("cards the app does not know are dropped and repeats removed, order kept", () => {
  assert.deepEqual(knownCards(["next_booking", "hologram", "shortcuts", "next_booking"]), ["next_booking", "shortcuts"]);
  assert.deepEqual(knownCards(undefined), []);
});

test("next booking is the soonest one that holds a place; the waitlist and cancelled are skipped", () => {
  const list = [
    booking("2026-10-20T10:00:00Z"),
    booking("2026-10-15T10:00:00Z", "waitlisted"),
    booking("2026-10-16T10:00:00Z", "booked", "cancelled"),
    booking("2026-10-17T10:00:00Z"),
    booking("2026-10-13T10:00:00Z"),
  ];
  assert.equal(nextBooking(list, now)?.starts_at, "2026-10-17T10:00:00Z");
  assert.equal(nextBooking([], now), undefined);
});

test("last visit is the latest finished, not cancelled or missed", () => {
  const list = [
    booking("2026-10-01T10:00:00Z", "checked_in"),
    booking("2026-10-10T10:00:00Z", "no_show"),
    booking("2026-10-12T10:00:00Z", "checked_in", "cancelled"),
    booking("2026-10-08T10:00:00Z", "checked_in"),
    booking("2026-10-20T10:00:00Z"),
  ];
  assert.equal(lastVisit(list, now)?.starts_at, "2026-10-08T10:00:00Z");
});

test("a cancellation inside the window is late", () => {
  assert.equal(isLateCancel("2026-10-14T11:00:00Z", 120, now), true);
  assert.equal(isLateCancel("2026-10-14T13:00:00Z", 120, now), false);
});

test("the calendar link carries the title, UTC times and place", () => {
  const url = new URL(calendarLink({ title: "Yoga", startsAt: "2026-10-17T17:00:00+03:00", endsAt: "2026-10-17T18:00:00+03:00", location: "Dizengoff 1" }));
  assert.equal(url.searchParams.get("text"), "Yoga");
  assert.equal(url.searchParams.get("dates"), "20261017T140000Z/20261017T150000Z");
  assert.equal(url.searchParams.get("location"), "Dizengoff 1");
});

test("updates are grouped as today, this week and earlier", () => {
  const items = ["2026-10-14", "2026-10-12", "2026-10-01", "2026-10-14"].map((d) => ({ d }));
  const groups = groupByRecency(items, (i) => i.d, (s) => s, "2026-10-14", "2026-10-07");
  assert.deepEqual(groups.map((g) => [g.key, g.items.length]), [["today", 2], ["week", 1], ["earlier", 1]]);
});
