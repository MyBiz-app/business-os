import type { components } from "@business-os/api-client";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { ColumnChart } from "@/components/charts/column-chart";
import { unwrap } from "@/lib/api";
import { addDays, formatDay, formatTime, todayIn } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { canReadReports } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { BusinessSwitcher } from "./business-switcher";

type MetricValue = components["schemas"]["MetricValue"];

const PERIODS = { "7": 7, "30": 30, "90": 90 } as const;
type Period = keyof typeof PERIODS;
const TILES = ["revenue", "active_clients", "attendance", "occupancy", "no_show_rate", "new_clients"] as const;

export default async function DashboardPage({ searchParams }: PageProps<"/dashboard">) {
  const t = await getTranslations();
  const locale = await getLocale();
  const { me, tenant, api, scope } = await getTenant();
  const query = await searchParams;
  const period: Period = query.period === "7" || query.period === "90" ? query.period : "30";
  const today = todayIn(tenant.time_zone);
  // Completed days only, so the comparison with the previous period is fair.
  const end = addDays(today, -1);
  const start = addDays(end, -(PERIODS[period] - 1));
  const reports = canReadReports(tenant);

  const canSeeSchedule = tenant.permissions.includes("schedule.read");
  const todays = canSeeSchedule
    ? unwrap(await api.GET("/sessions", { params: { ...scope, query: { start: today, days: 1 } } }))
    : [];
  const [metrics, revenue, attendance] = reports
    ? await Promise.all([
        api.GET("/metrics", { params: { ...scope, query: { start, end, keys: [...TILES] } } }).then(unwrap),
        api.GET("/metrics/{key}/series", { params: { ...scope, path: { key: "revenue" }, query: { start: addDays(end, -83), end, grain: "week" } } }).then(unwrap),
        api.GET("/metrics/{key}/series", { params: { ...scope, path: { key: "attendance" }, query: { start: addDays(end, -83), end, grain: "week" } } }).then(unwrap),
      ])
    : [[], [], []];

  const number = new Intl.NumberFormat(locale);
  const show = (metric: MetricValue, value: number | null) => {
    if (value === null) return "—";
    if (metric.unit === "money") return formatMoney(Math.round(value), tenant.currency, locale);
    if (metric.unit === "percent") return `${number.format(Math.round(value))}%`;
    return number.format(value);
  };
  const mine = todays.filter((session) => session.instructor_user_id === me.id);
  const sessionList = (sessions: typeof todays) => (
    <ul className="flex flex-col divide-y divide-border">
      {sessions.map((session) => (
        <li key={session.id}>
          <Link
            href={`/schedule/${session.id}`}
            className="flex items-center justify-between gap-3 py-2.5 hover:text-primary"
          >
            <span className="flex items-center gap-3">
              <span aria-hidden="true" className="size-2.5 rounded-full" style={{ backgroundColor: session.service.color ?? "var(--primary)" }} />
              <span className="tabular-nums" dir="ltr">
                {formatTime(session.starts_at, locale, tenant.time_zone)}
              </span>
              <span className={`font-medium ${session.status === "cancelled" ? "line-through" : ""}`}>
                {session.service.name}
              </span>
            </span>
            <span className="text-sm text-muted">
              {session.status === "cancelled"
                ? t("schedule.cancelled")
                : t("schedule.spotsLabel", { booked: session.booked, capacity: session.capacity })}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
  const weekLabel = (bucket: string) => formatDay(bucket, locale, { day: "numeric", month: "numeric" });

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-6 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold">{t("dashboard.welcome", { name: tenant.name })}</h1>
          <p className="text-muted">
            {t("dashboard.yourRole", { role: t(`roles.${tenant.role}`) })} · <span dir="ltr">{me.email}</span>
          </p>
        </div>
        <BusinessSwitcher current={tenant.id} memberships={me.memberships} />
      </div>

      {mine.length > 0 && (
        <section aria-labelledby="mine-heading" className="flex flex-col gap-3 rounded-2xl border border-primary bg-surface p-6">
          <h2 id="mine-heading" className="text-lg font-semibold">
            {t("dashboard.myClassesToday", { count: mine.length })}
          </h2>
          {sessionList(mine)}
        </section>
      )}

      {reports && (
        <section aria-labelledby="kpi-heading" className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="kpi-heading" className="text-lg font-semibold">
              {t("dashboard.kpis")}
            </h2>
            <nav aria-label={t("dashboard.period")} className="flex gap-1 rounded-lg border border-border bg-surface p-1 text-sm">
              {(Object.keys(PERIODS) as Period[]).map((value) => (
                <Link
                  key={value}
                  href={`/dashboard?period=${value}`}
                  aria-current={value === period ? "page" : undefined}
                  className={`rounded-md px-3 py-1 ${value === period ? "bg-primary text-on-primary" : "hover:bg-background"}`}
                >
                  {t("dashboard.lastDays", { count: PERIODS[value] })}
                </Link>
              ))}
            </nav>
          </div>
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {metrics.map((metric) => {
              const delta =
                metric.value !== null && metric.previous !== null ? metric.value - metric.previous : null;
              const better = delta === null || delta === 0 ? null : delta > 0 === metric.higher_is_better;
              const deltaText =
                delta === null
                  ? null
                  : metric.unit === "percent"
                    ? t("dashboard.points", { value: `${delta > 0 ? "+" : ""}${number.format(Math.round(delta))}` })
                    : metric.previous
                      ? `${delta > 0 ? "+" : ""}${number.format(Math.round((delta / metric.previous) * 100))}%`
                      : null;
              return (
                <li key={metric.key} className="flex flex-col gap-1 rounded-2xl border border-border bg-surface p-4">
                  <span className="text-sm text-muted">{t(`metrics.${metric.key}`)}</span>
                  <span className="text-3xl font-semibold">{show(metric, metric.value)}</span>
                  {deltaText && (
                    <span className={`text-sm ${better === null ? "text-muted" : better ? "text-success" : "text-danger"}`}>
                      <span aria-hidden="true">{delta! > 0 ? "▲" : delta! < 0 ? "▼" : "•"} </span>
                      {deltaText} <span className="text-muted">{t("dashboard.vsPrevious")}</span>
                      <span className="sr-only">
                        {" "}
                        ({better === null ? "" : better ? t("dashboard.better") : t("dashboard.worse")})
                      </span>
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {reports && (
        <section className="grid gap-6 rounded-2xl border border-border bg-surface p-6 lg:grid-cols-2">
          <ColumnChart
            title={t("dashboard.weeklyRevenue")}
            unit={{ kind: "money", currency: tenant.currency }}
            tableLabel={t("dashboard.showTable")}
            headers={[t("dashboard.weekOf"), t("metrics.revenue")]}
            columns={revenue.map((point) => ({
              key: point.bucket,
              label: weekLabel(point.bucket),
              value: point.value,
              display: formatMoney(Math.round(point.value), tenant.currency, locale),
            }))}
          />
          <ColumnChart
            title={t("dashboard.weeklyAttendance")}
            unit={{ kind: "count" }}
            tableLabel={t("dashboard.showTable")}
            headers={[t("dashboard.weekOf"), t("metrics.attendance")]}
            columns={attendance.map((point) => ({
              key: point.bucket,
              label: weekLabel(point.bucket),
              value: point.value,
              display: number.format(point.value),
            }))}
          />
        </section>
      )}

      {canSeeSchedule && <section aria-labelledby="today-heading" className="flex flex-col gap-3 rounded-2xl border border-border bg-surface p-6">
        <h2 id="today-heading" className="text-lg font-semibold">
          {t("dashboard.today")}
        </h2>
        {todays.length === 0 ? (
          <p className="text-muted">{t("dashboard.emptyToday")}</p>
        ) : (
          sessionList(todays)
        )}
      </section>}
    </main>
  );
}
