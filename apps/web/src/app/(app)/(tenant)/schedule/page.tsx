import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { termsOf } from "@business-os/verticals";

import { unwrap } from "@/lib/api";
import { addDays, dayOf, formatDay, formatTime, isDay, todayIn, weekStart } from "@/lib/dates";
import { canWriteSchedule } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { CopyWeek } from "./copy-week";

export default async function SchedulePage({ searchParams }: PageProps<"/schedule">) {
  const t = await getTranslations("schedule");
  const tAppointments = await getTranslations("appointments");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("schedule.read");
  const tAll = await getTranslations();
  const term = (key: "schedule" | "newSession" | "noSessions") => tAll(`terms.${termsOf(tenant.vertical)}.${key}` as "terms.fitness.schedule");
  const { week } = await searchParams;

  const today = todayIn(tenant.time_zone);
  const start = weekStart(isDay(week) ? week : today);
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));
  const [sessions, closedDays] = await Promise.all([
    api.GET("/sessions", { params: { ...scope, query: { start, days: 7 } } }).then(unwrap),
    api.GET("/closed-days", { params: { ...scope, query: { start } } }).then(unwrap),
  ]);
  const closed = new Map(closedDays.map((d) => [d.day, d]));
  const byDay = new Map(days.map((day) => [day, sessions.filter((s) => dayOf(s.starts_at, tenant.time_zone) === day)]));
  const range = `${formatDay(days[0], locale, { day: "numeric", month: "short" })} – ${formatDay(days[6], locale, { day: "numeric", month: "short", year: "numeric" })}`;

  return (
    <main className="enter flex w-full flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold">{term("schedule")}</h1>
          <p className="text-sm text-muted">{range}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <nav aria-label={term("schedule")} className="flex items-center gap-1 text-sm">
            <Link href={`/schedule?week=${addDays(start, -7)}`} className="btn-secondary px-3 py-2 font-medium">
              {t("previousWeek")}
            </Link>
            <Link href="/schedule" className="btn-secondary px-3 py-2 font-medium">
              {t("thisWeek")}
            </Link>
            <Link href={`/schedule?week=${addDays(start, 7)}`} className="btn-secondary px-3 py-2 font-medium">
              {t("nextWeek")}
            </Link>
          </nav>
          {canWriteSchedule(tenant) && (
            <Link href="/schedule/closed" className="btn-secondary px-3 py-2 text-sm font-medium">
              {t("closedDays")}
            </Link>
          )}
          {canWriteSchedule(tenant) && <CopyWeek key={start} weekStart={start} nextWeek={addDays(start, 7)} />}
          {tenant.permissions.includes("bookings.manage") && (
            <Link
              href={`/schedule/appointment?date=${start > today ? start : today}`}
              className="btn-secondary px-4 py-2.5"
            >
              {tAppointments("new")}
            </Link>
          )}
          {canWriteSchedule(tenant) && (
            <Link
              href={`/schedule/new?date=${start > today ? start : today}`}
              className="btn-primary px-4 py-2.5"
            >
              {term("newSession")}
            </Link>
          )}
        </div>
      </div>

      <ol className="enter-items grid gap-3 md:grid-cols-7">
        {days.map((day) => {
          const daySessions = byDay.get(day) ?? [];
          return (
            <li
              key={day}
              aria-label={formatDay(day, locale, { weekday: "long", day: "numeric", month: "long" })}
              className={`flex min-h-32 flex-col gap-2 p-2 ${day === today ? "card-accent" : "card"} ${closed.has(day) ? "bg-[repeating-linear-gradient(135deg,transparent_0_8px,color-mix(in_oklab,var(--foreground)_4%,transparent)_8px_16px)]" : ""}`}
            >
              <div className={`flex items-center justify-between gap-1 px-1 pt-1 text-sm font-semibold ${day === today ? "text-primary" : ""}`}>
                {formatDay(day, locale, { weekday: "short", day: "numeric" })}
                {daySessions.length > 0 && (
                  <span aria-hidden="true" className="rounded-full bg-foreground/6 px-1.5 text-xs font-medium text-muted">
                    {daySessions.length}
                  </span>
                )}
              </div>
              {closed.has(day) && (
                <p className="rounded-lg bg-warning/12 px-2 py-1 text-xs font-semibold" dir="auto">
                  {t("closedDay")}
                  {closed.get(day)?.reason && ` · ${closed.get(day)?.reason}`}
                </p>
              )}
              {daySessions.length === 0 ? (
                <p className="px-1 text-xs text-muted">{term("noSessions")}</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {daySessions.map((session) => {
                    const cancelled = session.status === "cancelled";
                    const color = session.service.color ?? "var(--primary)";
                    const fill = session.capacity ? Math.min(session.booked / session.capacity, 1) : 0;
                    return (
                      <li key={session.id}>
                        <Link
                          href={`/schedule/${session.id}`}
                          className={`flex flex-col gap-0.5 rounded-xl border-s-4 px-2.5 py-2 text-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md ${cancelled ? "opacity-60" : ""}`}
                          style={{
                            borderInlineStartColor: color,
                            background: `color-mix(in oklab, ${color} 9%, var(--surface))`,
                          }}
                        >
                          <span className="font-medium tabular-nums" dir="ltr">
                            {formatTime(session.starts_at, locale, tenant.time_zone)}–{formatTime(session.ends_at, locale, tenant.time_zone)}
                          </span>
                          <span className={`font-semibold ${cancelled ? "line-through" : ""}`}>{session.service.name}</span>
                          {session.room_name && <span className="text-xs text-muted">{session.room_name}</span>}
                          {session.booking_mode === "appointment" ? (
                            <span className="truncate text-xs font-medium" dir="auto">
                              {cancelled ? t("cancelled") : session.appointment_client}
                            </span>
                          ) : (
                            <span className="text-xs text-muted" aria-label={t("spotsLabel", { booked: session.booked, capacity: session.capacity })}>
                              {cancelled ? t("cancelled") : t("spots", { booked: session.booked, capacity: session.capacity })}
                            </span>
                          )}
                          {!cancelled && session.booking_mode === "class" && (
                            <span aria-hidden="true" className="mt-1 h-1 overflow-hidden rounded-full bg-foreground/8">
                              <span className="block h-full rounded-full" style={{ width: `${fill * 100}%`, backgroundColor: color }} />
                            </span>
                          )}
                          {!cancelled && session.waitlisted > 0 && (
                            <span className="text-xs text-muted">{t("waitlisted", { count: session.waitlisted })}</span>
                          )}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              )}
            </li>
          );
        })}
      </ol>
    </main>
  );
}
