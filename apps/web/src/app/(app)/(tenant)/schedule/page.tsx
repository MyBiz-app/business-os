import { ChevronLeft, ChevronRight } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { termsOf } from "@business-os/verticals";

import { LiveRefresh } from "@/components/live-refresh";
import { unwrap } from "@/lib/api";
import { branchColor, minutesIn } from "@/lib/calendar";
import { addDays, dayOf, formatDay, formatTime, isDay, todayIn, toApiWeekday, weekdayOf, weekStart } from "@/lib/dates";
import { canWriteSchedule } from "@/lib/permissions";
import { getBranches, getTenantFor } from "@/lib/tenant";

import { TimeGrid, type GridEvent, type GridShift } from "./_grid/time-grid";
import { CopyWeek } from "./copy-week";

type View = "day" | "week";

export default async function SchedulePage({ searchParams }: PageProps<"/schedule">) {
  const t = await getTranslations("schedule");
  const tAppointments = await getTranslations("appointments");
  const tAll = await getTranslations();
  const locale = await getLocale();
  const { tenant, api, scope, branch } = await getTenantFor("schedule.read");
  const term = (key: "schedule" | "newSession" | "noSessions") => tAll(`terms.${termsOf(tenant.vertical)}.${key}` as "terms.fitness.schedule");
  const query = await searchParams;
  const view: View = query.view === "day" ? "day" : "week";
  const today = todayIn(tenant.time_zone);
  // `week` is kept for older links.
  const anchor = isDay(query.date) ? query.date : isDay(query.week) ? query.week : today;
  const start = view === "day" ? anchor : weekStart(anchor);
  const days = Array.from({ length: view === "day" ? 1 : 7 }, (_, i) => addDays(start, i));
  const step = view === "day" ? 1 : 7;

  // Branches: the current one from the menu, or several picked here to see side by side.
  const branches = await getBranches();
  const picked = typeof query.branches === "string" ? query.branches.split(",").filter((id) => branches.some((b) => b.id === id)) : [];
  const shown = picked.length > 0 ? picked : branch ? [branch] : branches.map((b) => b.id);
  const multi = picked.length > 0;
  // Picking branches here looks across them, so the menu's single branch is not applied.
  const params = multi ? { header: { "X-Tenant-Id": scope.header["X-Tenant-Id"] } } : scope;
  const colorOf = new Map(branches.map((b, i) => [b.id, branchColor(i)]));
  const nameOf = new Map(branches.map((b) => [b.id, b.name]));
  const oneBranch = shown.length === 1 ? shown[0] : branches.length === 1 ? branches[0].id : null;

  const [sessions, closedDays, shifts, hours] = await Promise.all([
    api.GET("/sessions", { params: { ...params, query: { start, days: days.length, ...(multi ? { location_id: picked } : {}) } } }).then(unwrap),
    api.GET("/closed-days", { params: { ...params, query: { start } } }).then(unwrap),
    api.GET("/shifts", { params: { ...params, query: { start, days: days.length, ...(multi ? { location_id: picked } : {}) } } }).then((r) => r.data ?? []),
    oneBranch && tenant.permissions.includes("catalog.read")
      ? api.GET("/locations/{location_id}/hours", { params: { ...params, path: { location_id: oneBranch } } }).then((r) => r.data ?? null)
      : null,
  ]);

  const showBranch = shown.length > 1 && branches.length > 1;
  const events: GridEvent[] = sessions.map((session) => {
    const location = session.location_id ?? null;
    const day = dayOf(session.starts_at, tenant.time_zone);
    const startsAt = minutesIn(session.starts_at, tenant.time_zone);
    const cancelled = session.status === "cancelled";
    return {
      id: session.id,
      href: `/schedule/${session.id}`,
      day,
      start: startsAt,
      // Past midnight: drawn to the end of its day.
      end: dayOf(session.ends_at, tenant.time_zone) === day ? Math.max(minutesIn(session.ends_at, tenant.time_zone), startsAt + 15) : 24 * 60,
      time: `${formatTime(session.starts_at, locale, tenant.time_zone)}–${formatTime(session.ends_at, locale, tenant.time_zone)}`,
      title: session.service.name,
      detail: cancelled
        ? t("cancelled")
        : session.booking_mode === "appointment"
          ? (session.appointment_client ?? null)
          : t("spotsLabel", { booked: session.booked, capacity: session.capacity }),
      color: session.service.color ?? "var(--primary)",
      branch: showBranch && location ? { name: nameOf.get(location) ?? "", color: colorOf.get(location) ?? "var(--primary)" } : null,
      cancelled,
    };
  });
  const gridShifts: GridShift[] = shifts.map((shift) => ({
    id: shift.id,
    day: dayOf(shift.starts_at, tenant.time_zone),
    start: minutesIn(shift.starts_at, tenant.time_zone),
    end: dayOf(shift.ends_at, tenant.time_zone) === dayOf(shift.starts_at, tenant.time_zone) ? minutesIn(shift.ends_at, tenant.time_zone) : 24 * 60,
    userId: shift.user_id,
    name: shift.user_name,
    avatar: null,
    label: `${formatTime(shift.starts_at, locale, tenant.time_zone)}–${formatTime(shift.ends_at, locale, tenant.time_zone)}${shift.position ? ` · ${shift.position}` : ""}`,
    warn: shift.on_time_off || shift.outside_hours,
  }));
  const open = hours
    ? Object.fromEntries(
        days.map((day) => [
          day,
          hours.intervals
            .filter((i) => i.weekday === toApiWeekday(weekdayOf(day)))
            .map((i) => ({ start: toMinutes(i.opens), end: toMinutes(i.closes) })),
        ]),
      )
    : null;
  const closed = Object.fromEntries(closedDays.map((d) => [d.day, d.reason ?? null]));

  const range =
    view === "day"
      ? formatDay(start, locale, { weekday: "long", day: "numeric", month: "long", year: "numeric" })
      : `${formatDay(days[0], locale, { day: "numeric", month: "short" })} – ${formatDay(days[6], locale, { day: "numeric", month: "short", year: "numeric" })}`;
  const link = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams();
    const merged = { view, date: anchor, branches: picked.join(",") || null, ...changes };
    for (const [key, value] of Object.entries(merged)) if (value) next.set(key, value);
    return `/schedule?${next.toString()}`;
  };
  const toggleBranch = (id: string) => {
    const set = new Set(picked.length > 0 ? picked : shown);
    if (set.has(id)) set.delete(id);
    else set.add(id);
    // None or all of them: back to the usual view.
    return link({ branches: set.size > 0 && set.size < branches.length ? [...set].join(",") : null });
  };

  return (
    <main className="enter flex w-full flex-1 flex-col gap-5 px-4 py-8 sm:px-6 sm:py-10">
      <LiveRefresh />
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold">{term("schedule")}</h1>
          <p className="text-sm text-muted">{range}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {canWriteSchedule(tenant) && (
            <Link href="/schedule/closed" className="btn-ghost px-3 py-2 text-sm">
              {t("closedDays")}
            </Link>
          )}
          {canWriteSchedule(tenant) && view === "week" && <CopyWeek key={start} weekStart={start} nextWeek={addDays(start, 7)} />}
          {tenant.permissions.includes("bookings.manage") && (
            <Link href={`/schedule/appointment?date=${start > today ? start : today}`} className="btn-secondary px-4 py-2.5 text-sm">
              {tAppointments("new")}
            </Link>
          )}
          {canWriteSchedule(tenant) && (
            <Link href={`/schedule/new?date=${start > today ? start : today}`} className="btn-primary px-4 py-2.5 text-sm">
              {term("newSession")}
            </Link>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <nav aria-label={term("schedule")} className="flex items-center gap-1.5">
          <Link href={link({ date: addDays(start, -step) })} aria-label={view === "day" ? t("previousDay") : t("previousWeek")} className="btn-secondary size-9">
            <ChevronLeft aria-hidden="true" className="size-4 rtl:rotate-180" />
          </Link>
          <Link href={link({ date: today })} className="btn-secondary px-3 py-2 text-sm">
            {t("today")}
          </Link>
          <Link href={link({ date: addDays(start, step) })} aria-label={view === "day" ? t("nextDay") : t("nextWeek")} className="btn-secondary size-9">
            <ChevronRight aria-hidden="true" className="size-4 rtl:rotate-180" />
          </Link>
          <div role="group" aria-label={t("view")} className="ms-2 flex rounded-xl border border-border bg-surface p-0.5 text-sm">
            {(["day", "week"] as const).map((option) => (
              <Link
                key={option}
                href={link({ view: option })}
                aria-current={view === option ? "page" : undefined}
                className={`rounded-lg px-3 py-1.5 font-medium transition-colors ${view === option ? "bg-primary/12 text-primary" : "text-muted hover:text-foreground"}`}
              >
                {t(option === "day" ? "dayView" : "weekView")}
              </Link>
            ))}
          </div>
        </nav>
        {branches.length > 1 && (
          <nav aria-label={t("branches")} className="flex flex-wrap items-center gap-1.5">
            {branches.map((b) => {
              const on = shown.includes(b.id);
              return (
                <Link
                  key={b.id}
                  href={toggleBranch(b.id)}
                  aria-pressed={on}
                  className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm transition-colors ${on ? "border-transparent bg-foreground/8 font-medium" : "border-border text-muted hover:text-foreground"}`}
                >
                  <span aria-hidden="true" className={`size-2.5 rounded-full ${on ? "" : "opacity-40"}`} style={{ background: colorOf.get(b.id) }} />
                  <span dir="auto">{b.name}</span>
                </Link>
              );
            })}
          </nav>
        )}
      </div>

      {/* On phones: jump straight to a day of the week. */}
      {view === "week" && (
        <nav aria-label={t("jumpToDay")} className="md:hidden">
          <ul className="grid grid-cols-7 gap-1.5">
            {days.map((day) => (
              <li key={day}>
                <Link
                  href={link({ view: "day", date: day })}
                  aria-current={day === today ? "date" : undefined}
                  className={`flex flex-col items-center rounded-xl border py-1.5 text-xs transition-colors ${day === today ? "border-primary bg-primary text-on-primary" : "border-border bg-surface hover:bg-foreground/5"}`}
                >
                  <span>{formatDay(day, locale, { weekday: "short" })}</span>
                  <span className="text-base font-semibold tabular-nums">{formatDay(day, locale, { day: "numeric" })}</span>
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}

      <TimeGrid
        days={days}
        timeZone={tenant.time_zone}
        locale={locale}
        events={events}
        shifts={gridShifts}
        closed={closed}
        open={open}
        labels={{ now: t("now"), closed: t("closedDay"), shifts: tAll("shifts.title"), empty: term("noSessions") }}
      />
      {gridShifts.length > 0 && <p className="text-xs text-muted">{t("shiftsLegend")}</p>}
    </main>
  );
}

function toMinutes(clock: string): number {
  const [hours, minutes] = clock.split(":").map(Number);
  return hours * 60 + minutes;
}

