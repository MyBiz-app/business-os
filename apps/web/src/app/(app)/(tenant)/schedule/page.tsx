import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { unwrap } from "@/lib/api";
import { addDays, dayOf, formatDay, formatTime, isDay, todayIn, weekStart } from "@/lib/dates";
import { canWriteSchedule } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

export default async function SchedulePage({ searchParams }: PageProps<"/schedule">) {
  const t = await getTranslations("schedule");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenant();
  const { week } = await searchParams;

  const today = todayIn(tenant.time_zone);
  const start = weekStart(isDay(week) ? week : today);
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));
  const sessions = unwrap(await api.GET("/sessions", { params: { ...scope, query: { start, days: 7 } } }));
  const byDay = new Map(days.map((day) => [day, sessions.filter((s) => dayOf(s.starts_at, tenant.time_zone) === day)]));
  const range = `${formatDay(days[0], locale, { day: "numeric", month: "short" })} – ${formatDay(days[6], locale, { day: "numeric", month: "short", year: "numeric" })}`;

  return (
    <main className="flex w-full flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold">{t("title")}</h1>
          <p className="text-sm text-muted">{range}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <nav aria-label={t("title")} className="flex items-center gap-1 text-sm">
            <Link href={`/schedule?week=${addDays(start, -7)}`} className="rounded-lg border border-border px-3 py-2">
              {t("previousWeek")}
            </Link>
            <Link href="/schedule" className="rounded-lg border border-border px-3 py-2">
              {t("thisWeek")}
            </Link>
            <Link href={`/schedule?week=${addDays(start, 7)}`} className="rounded-lg border border-border px-3 py-2">
              {t("nextWeek")}
            </Link>
          </nav>
          {canWriteSchedule(tenant.role) && (
            <Link
              href={`/schedule/new?date=${start > today ? start : today}`}
              className="rounded-lg bg-primary px-4 py-2.5 font-semibold text-on-primary"
            >
              {t("newSession")}
            </Link>
          )}
        </div>
      </div>

      <ol className="grid gap-3 md:grid-cols-7">
        {days.map((day) => {
          const daySessions = byDay.get(day) ?? [];
          return (
            <li
              key={day}
              aria-label={formatDay(day, locale, { weekday: "long", day: "numeric", month: "long" })}
              className={`flex min-h-32 flex-col gap-2 rounded-2xl border p-2 ${day === today ? "border-primary" : "border-border"}`}
            >
              <div className={`px-1 text-sm font-semibold ${day === today ? "text-primary" : ""}`}>
                {formatDay(day, locale, { weekday: "short", day: "numeric" })}
              </div>
              {daySessions.length === 0 ? (
                <p className="px-1 text-xs text-muted">{t("noSessions")}</p>
              ) : (
                <ul className="flex flex-col gap-2">
                  {daySessions.map((session) => {
                    const cancelled = session.status === "cancelled";
                    return (
                      <li key={session.id}>
                        <Link
                          href={`/schedule/${session.id}`}
                          className={`flex flex-col gap-0.5 rounded-xl border-s-4 bg-surface px-2.5 py-2 text-sm hover:ring-1 hover:ring-primary ${cancelled ? "opacity-60" : ""}`}
                          style={{ borderInlineStartColor: session.service.color ?? "var(--primary)" }}
                        >
                          <span className="font-medium tabular-nums" dir="ltr">
                            {formatTime(session.starts_at, locale, tenant.time_zone)}–{formatTime(session.ends_at, locale, tenant.time_zone)}
                          </span>
                          <span className={`font-semibold ${cancelled ? "line-through" : ""}`}>{session.service.name}</span>
                          {session.room_name && <span className="text-xs text-muted">{session.room_name}</span>}
                          <span className="text-xs text-muted" aria-label={t("spotsLabel", { booked: session.booked, capacity: session.capacity })}>
                            {cancelled ? t("cancelled") : t("spots", { booked: session.booked, capacity: session.capacity })}
                          </span>
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
