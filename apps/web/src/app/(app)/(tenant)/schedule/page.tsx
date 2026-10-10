import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { termsOf } from "@business-os/verticals";

import { DateJump } from "@/components/calendar-board/date-jump";
import { MonthGrid } from "@/components/calendar-board/month-grid";
import { TimeGrid, type GridEvent, type GridLane, type GridShift } from "@/components/calendar-board/time-grid";
import { LiveRefresh } from "@/components/live-refresh";
import { unwrap } from "@/lib/api";
import { branchColor, isBoardRange, LANE_LIMIT, limitLanes, minutesIn, type BoardRange } from "@/lib/calendar";
import { addDays, addMonths, dayOf, formatDay, formatTime, isDay, monthGrid, monthStart, todayIn, toApiWeekday, weekdayOf, weekStart } from "@/lib/dates";
import { canManageSettings, canWriteSchedule } from "@/lib/permissions";
import { getBranches, getTenantFor } from "@/lib/tenant";

import { CopyWeek } from "./copy-week";
import { SaveDefault } from "./save-default";

export default async function SchedulePage({ searchParams }: PageProps<"/schedule">) {
  const t = await getTranslations("schedule");
  const tAppointments = await getTranslations("appointments");
  const tAll = await getTranslations();
  const locale = await getLocale();
  const { tenant, api, scope, branch } = await getTenantFor("schedule.read");
  const term = (key: "schedule" | "newSession" | "noSessions") => tAll(`terms.${termsOf(tenant.vertical)}.${key}` as "terms.fitness.schedule");
  const query = await searchParams;
  // The business's own default opens the page; a link with a view or branches always wins.
  const view: BoardRange = isBoardRange(query.view) ? query.view : ((tenant.schedule_default_view ?? "week") as BoardRange);
  const today = todayIn(tenant.time_zone);
  // `week` is kept for older links.
  const anchor = isDay(query.date) ? query.date : isDay(query.week) ? query.week : today;
  const month = monthGrid(anchor);
  const start = view === "day" ? anchor : view === "week" ? weekStart(anchor) : month.start;
  const count = view === "day" ? 1 : view === "week" ? 7 : month.days;
  const days = Array.from({ length: count }, (_, i) => addDays(start, i));

  // Branches: side by side as lanes. Picked here, else the menu's branch, else the business's default.
  const branches = await getBranches();
  const known = (ids: string[]) => ids.filter((id) => branches.some((b) => b.id === id));
  const explicit = typeof query.branches === "string";
  const asked = explicit ? known(String(query.branches).split(",")) : branch ? [] : known(tenant.schedule_default_branches ?? []);
  let laneIds = limitLanes(asked, view);
  // Nothing picked and no menu branch: all of them side by side when they fit (a month: the first).
  if (laneIds.length === 0 && !branch && branches.length > 1 && (view === "month" || branches.length <= LANE_LIMIT[view])) {
    laneIds = limitLanes(branches.map((b) => b.id), view);
  }
  const multi = laneIds.length > 0;
  const shown = multi ? laneIds : branch ? [branch] : branches.map((b) => b.id);
  const lanes: GridLane[] = laneIds.length > 1 ? laneIds.map((id) => ({ id, name: branches.find((b) => b.id === id)?.name ?? "", color: "" })) : [];
  const colorOf = new Map(branches.map((b, i) => [b.id, branchColor(i)]));
  for (const lane of lanes) lane.color = colorOf.get(lane.id) ?? "var(--primary)";
  const nameOf = new Map(branches.map((b) => [b.id, b.name]));
  // Picking branches here looks across them, so the menu's single branch is not applied.
  const params = multi ? { header: { "X-Tenant-Id": scope.header["X-Tenant-Id"] } } : scope;
  const filter = multi ? { location_id: laneIds } : {};
  const hoursOf = multi ? laneIds : branch ? [branch] : branches.length === 1 ? [branches[0].id] : [];
  const showHours = view !== "month" && tenant.permissions.includes("catalog.read");

  const [sessions, closedDays, shifts, hours] = await Promise.all([
    api.GET("/sessions", { params: { ...params, query: { start, days: days.length, ...filter } } }).then(unwrap),
    api.GET("/closed-days", { params: { ...params, query: { start } } }).then(unwrap),
    view === "month" ? [] : api.GET("/shifts", { params: { ...params, query: { start, days: days.length, ...filter } } }).then((r) => r.data ?? []),
    showHours
      ? Promise.all(hoursOf.map((id) => api.GET("/locations/{location_id}/hours", { params: { ...params, path: { location_id: id } } }).then((r) => [id, r.data ?? null] as const)))
      : [],
  ]);

  const mergedBranches = !multi && shown.length > 1;
  const events: GridEvent[] = sessions.map((session) => {
    const location = session.location_id ?? null;
    const day = dayOf(session.starts_at, tenant.time_zone);
    const startsAt = minutesIn(session.starts_at, tenant.time_zone);
    const cancelled = session.status === "cancelled";
    return {
      id: session.id,
      href: `/schedule/${session.id}`,
      day,
      laneId: location,
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
      branch: mergedBranches && location ? { name: nameOf.get(location) ?? "", color: colorOf.get(location) ?? "var(--primary)" } : null,
      cancelled,
    };
  });
  const gridShifts: GridShift[] = shifts.map((shift) => ({
    id: shift.id,
    day: dayOf(shift.starts_at, tenant.time_zone),
    laneId: shift.location_id,
    start: minutesIn(shift.starts_at, tenant.time_zone),
    end: dayOf(shift.ends_at, tenant.time_zone) === dayOf(shift.starts_at, tenant.time_zone) ? minutesIn(shift.ends_at, tenant.time_zone) : 24 * 60,
    userId: shift.user_id,
    name: shift.user_name,
    avatar: null,
    label: `${formatTime(shift.starts_at, locale, tenant.time_zone)}–${formatTime(shift.ends_at, locale, tenant.time_zone)}${shift.position ? ` · ${shift.position}` : ""}`,
    warn: shift.on_time_off || shift.outside_hours,
  }));
  // Opening hours per branch lane (`""`: the single column).
  const open = hours.length
    ? Object.fromEntries(
        hours.flatMap(([id, opening]) =>
          opening
            ? [
                [
                  lanes.length > 1 ? id : "",
                  Object.fromEntries(
                    days.map((day) => [
                      day,
                      opening.intervals.filter((i) => i.weekday === toApiWeekday(weekdayOf(day))).map((i) => ({ start: toMinutes(i.opens), end: toMinutes(i.closes) })),
                    ]),
                  ),
                ] as const,
              ]
            : [],
        ),
      )
    : null;
  const closed = Object.fromEntries(closedDays.map((d) => [d.day, d.reason ?? null]));

  const range =
    view === "day"
      ? formatDay(start, locale, { weekday: "long", day: "numeric", month: "long", year: "numeric" })
      : view === "week"
        ? `${formatDay(days[0], locale, { day: "numeric", month: "short" })} – ${formatDay(days[6], locale, { day: "numeric", month: "short", year: "numeric" })}`
        : formatDay(monthStart(anchor), locale, { month: "long", year: "numeric" });
  const link = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams();
    const merged = { view: isBoardRange(query.view) ? query.view : null, date: anchor === today ? null : anchor, branches: explicit ? String(query.branches) : null, ...changes };
    for (const [key, value] of Object.entries(merged)) if (value) next.set(key, value);
    const text = next.toString();
    return text ? `/schedule?${text}` : "/schedule";
  };
  // A view's own address (the stored default can differ from what the page shows).
  const viewLink = (option: BoardRange) => link({ view: option });
  const limit = LANE_LIMIT[view];
  const toggleBranch = (id: string): string | null => {
    const picks = multi ? laneIds : branch ? [branch] : [];
    if (picks.includes(id)) {
      const rest = picks.filter((x) => x !== id);
      return link({ branches: rest.length > 0 ? rest.join(",") : "menu" });
    }
    if (picks.length >= limit) return limit === 1 ? link({ branches: id }) : null;
    return link({ branches: [...picks, id].join(",") });
  };
  const branchStep = view === "day" ? 1 : view === "week" ? 7 : 0;
  const prev = view === "month" ? addMonths(anchor, -1) : addDays(start, -branchStep);
  const next = view === "month" ? addMonths(anchor, 1) : addDays(start, branchStep);
  const stepName = t(view === "day" ? "stepDay" : view === "week" ? "stepWeek" : "stepMonth");
  const includesToday = days.includes(today) && (view !== "month" || today.startsWith(anchor.slice(0, 7)));
  const customized = isBoardRange(query.view) || explicit || isDay(query.date) || isDay(query.week);

  return (
    <main className="enter flex w-full flex-1 flex-col gap-5 px-4 py-8 sm:px-6 sm:py-10">
      <LiveRefresh />
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold">{term("schedule")}</h1>
          <p className="flex items-center gap-2 text-sm text-muted">
            <span>{range}</span>
            {includesToday && <span className="rounded-full bg-primary/12 px-2 py-0.5 text-xs font-semibold text-primary">{t("today")}</span>}
          </p>
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
        <nav aria-label={term("schedule")} className="flex flex-wrap items-center gap-1.5">
          {view === "day" && (
            <Link href={link({ date: addDays(start, -7) })} aria-label={t("previousWeek")} title={t("previousWeek")} className="btn-secondary h-9 gap-1 px-2 text-sm">
              <ChevronsLeft aria-hidden="true" className="size-4 rtl:rotate-180" />
              <span className="hidden sm:inline">{t("stepWeek")}</span>
            </Link>
          )}
          <Link
            href={link({ date: prev })}
            aria-label={view === "day" ? t("previousDay") : view === "week" ? t("previousWeek") : t("previousMonth")}
            className="btn-secondary h-9 gap-1 px-2 text-sm"
          >
            <ChevronLeft aria-hidden="true" className="size-4 rtl:rotate-180" />
            <span className="hidden sm:inline">{stepName}</span>
          </Link>
          <Link href={link({ date: null })} aria-current={includesToday ? "date" : undefined} className="btn-secondary h-9 px-3 text-sm font-semibold">
            {t("today")}
          </Link>
          <Link
            href={link({ date: next })}
            aria-label={view === "day" ? t("nextDay") : view === "week" ? t("nextWeek") : t("nextMonth")}
            className="btn-secondary h-9 gap-1 px-2 text-sm"
          >
            <span className="hidden sm:inline">{stepName}</span>
            <ChevronRight aria-hidden="true" className="size-4 rtl:rotate-180" />
          </Link>
          {view === "day" && (
            <Link href={link({ date: addDays(start, 7) })} aria-label={t("nextWeek")} title={t("nextWeek")} className="btn-secondary h-9 gap-1 px-2 text-sm">
              <span className="hidden sm:inline">{t("stepWeek")}</span>
              <ChevronsRight aria-hidden="true" className="size-4 rtl:rotate-180" />
            </Link>
          )}
          <DateJump value={anchor} href={link({ date: "__day__" })} label={t("goToDate")} />
          <div role="group" aria-label={t("view")} className="ms-1 flex rounded-xl border border-border bg-surface p-0.5 text-sm">
            {(["day", "week", "month"] as const).map((option) => (
              <Link
                key={option}
                href={viewLink(option)}
                aria-current={view === option ? "page" : undefined}
                className={`rounded-lg px-3 py-1.5 font-medium transition-colors ${view === option ? "bg-primary/12 text-primary" : "text-muted hover:text-foreground"}`}
              >
                {t(option === "day" ? "dayView" : option === "week" ? "weekView" : "monthView")}
              </Link>
            ))}
          </div>
        </nav>
        {customized && (
          <Link href="/schedule" className="text-sm text-muted underline-offset-4 hover:text-foreground hover:underline">
            {t("resetView")}
          </Link>
        )}
      </div>

      {branches.length > 1 && (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <nav aria-label={t("branches")} className="flex flex-wrap items-center gap-1.5">
            {branches.map((b) => {
              const on = shown.includes(b.id);
              const href = toggleBranch(b.id);
              const className = `flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm transition-colors ${on ? "border-transparent bg-foreground/8 font-medium" : "border-border text-muted"} ${href ? "hover:text-foreground" : "cursor-not-allowed opacity-50"}`;
              const content = (
                <>
                  <span aria-hidden="true" className={`size-2.5 rounded-full ${on ? "" : "opacity-40"}`} style={{ background: colorOf.get(b.id) }} />
                  <span dir="auto">{b.name}</span>
                </>
              );
              return href ? (
                <Link key={b.id} href={href} aria-pressed={on} className={className}>
                  {content}
                </Link>
              ) : (
                <span key={b.id} aria-disabled="true" title={t("branchLimit", { count: limit })} className={className}>
                  {content}
                </span>
              );
            })}
            <span className="ms-1 text-xs text-muted">{view === "month" ? t("monthOneBranch") : t("branchLimit", { count: limit })}</span>
          </nav>
          {canManageSettings(tenant) && <SaveDefault view={view} branches={laneIds} />}
        </div>
      )}
      {branches.length <= 1 && canManageSettings(tenant) && view !== (tenant.schedule_default_view ?? "week") && <SaveDefault view={view} branches={[]} />}

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

      {view === "month" ? (
        <MonthGrid
          start={start}
          days={count}
          month={anchor.slice(0, 7)}
          today={today}
          locale={locale}
          events={events}
          closed={closed}
          labels={{ closed: t("closedDay"), more: t.raw("more") as string, empty: term("noSessions") }}
          dayHref={link({ view: "day", date: "__day__" })}
        />
      ) : (
        <TimeGrid
          days={days}
          timeZone={tenant.time_zone}
          locale={locale}
          events={events}
          shifts={gridShifts}
          lanes={lanes}
          closed={closed}
          open={open}
          labels={{ now: t("now"), closed: t("closedDay"), shifts: tAll("shifts.title"), empty: term("noSessions"), more: t.raw("more") as string, onShift: t("onShift") }}
          dayHref={view === "week" ? link({ view: "day", date: "__day__" }) : null}
        />
      )}
      {gridShifts.length > 0 && <p className="text-xs text-muted">{t("shiftsLegend")}</p>}
    </main>
  );
}

function toMinutes(clock: string): number {
  const [hours, minutes] = clock.split(":").map(Number);
  return hours * 60 + minutes;
}
