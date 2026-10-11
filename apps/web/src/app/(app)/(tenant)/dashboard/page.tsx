import type { components } from "@business-os/api-client";
import { ArrowDownRight, ArrowRight, ArrowUpRight, Banknote, CalendarCheck, CreditCard, Gauge, Luggage, Minus, UserPlus, Users, UserX } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { AttentionPanel } from "./attention-panel";
import { usageWarnings } from "@business-os/i18n/usage";
import { termsOf } from "@business-os/verticals";

import { ColumnChart } from "@/components/charts/column-chart";
import { GettingStartedCard } from "@/components/getting-started";
import { LiveRefresh } from "@/components/live-refresh";
import { CountUp } from "@/components/motion/count-up";
import { unwrap } from "@/lib/api";
import { addDays, formatDay, formatTime, todayIn } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { canManageSettings, canReadReports } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";
import { coverSrc } from "@/lib/workspace";

import { isolate } from "@/lib/bidi";

type MetricValue = components["schemas"]["MetricValue"];

const PERIODS = { "7": 7, "30": 30, "90": 90 } as const;
type Period = keyof typeof PERIODS;
const TILES = ["revenue", "active_clients", "attendance", "occupancy", "no_show_rate", "new_clients"] as const;
const TILE_ICONS = {
  revenue: Banknote,
  active_clients: Users,
  attendance: CalendarCheck,
  occupancy: Gauge,
  no_show_rate: UserX,
  new_clients: UserPlus,
} as const;

/** The part of the day in the business's time zone, for the greeting. */
function partOfDay(timeZone: string): "morning" | "afternoon" | "evening" | "night" {
  const hour = Number(new Intl.DateTimeFormat("en-GB", { hour: "numeric", hourCycle: "h23", timeZone }).format(new Date()));
  return hour < 5 ? "night" : hour < 12 ? "morning" : hour < 17 ? "afternoon" : hour < 22 ? "evening" : "night";
}

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
  const series = (key: "revenue" | "attendance") =>
    api.GET("/metrics/{key}/series", { params: { ...scope, path: { key }, query: { start: addDays(end, -83), end, grain: "week" } } }).then(unwrap);
  // Everything at once: each request waits on the API, none waits on another.
  const [todays, [metrics, revenue, attendance], billing, setup] = await Promise.all([
    canSeeSchedule ? api.GET("/sessions", { params: { ...scope, query: { start: today, days: 1 } } }).then(unwrap) : [],
    reports
      ? Promise.all([api.GET("/metrics", { params: { ...scope, query: { start, end, keys: [...TILES] } } }).then(unwrap), series("revenue"), series("attendance")])
      : ([[], [], []] as const),
    // The MyBiz subscription: remind whoever manages settings before the trial ends or when an
    // invoice is unpaid.
    canManageSettings(tenant) ? api.GET("/billing", { params: scope }).then((r) => r.data) : undefined,
    // The first-steps checklist, for whoever sets the business up, until it's all done.
    canManageSettings(tenant) ? api.GET("/tenants/current/getting-started", { params: scope }).then((r) => r.data) : undefined,
  ]);
  const welcome = query.welcome === "1";
  const billingNotice = !billing
    ? null
    : billing.balance_due > 0
      ? t("billing.dashboardDue", { amount: formatMoney(billing.balance_due, billing.estimate.currency, locale) })
      : billing.in_trial && !billing.payment_method && billing.trial_days_left <= 7
        ? t("billing.dashboardTrial", { days: billing.trial_days_left })
        : null;

  // Space and messages: warn from 80% of the bundle (#104). Messages keep going over it; new
  // files stop.
  const usageNotices = billing ? usageWarnings(billing.usage).map(({ key, percent }) => t(`billing.usage.${key}`, { percent })) : [];

  const number = new Intl.NumberFormat(locale);
  // Rounded, with a sign; never "-0".
  const signed = (value: number) => {
    const rounded = Math.round(value) || 0;
    return `${rounded > 0 ? "+" : ""}${number.format(rounded)}`;
  };
  const show = (metric: MetricValue, value: number | null) => {
    if (value === null) return "—";
    if (metric.unit === "money") return formatMoney(Math.round(value), tenant.currency, locale);
    if (metric.unit === "percent") return `${number.format(Math.round(value))}%`;
    return number.format(value);
  };
  const mine = todays.filter((session) => session.instructor_user_id === me.id);
  const sessionList = (sessions: typeof todays) => (
    <ul className="enter-items flex flex-col gap-2">
      {sessions.map((session) => {
        const fill = session.capacity ? Math.min(session.booked / session.capacity, 1) : 0;
        const color = session.service.color ?? "var(--primary)";
        return (
          <li key={session.id}>
            <Link
              href={`/schedule/${session.id}`}
              className="group flex items-center gap-4 rounded-xl border border-transparent px-3 py-2.5 transition-colors hover:border-border hover:bg-background"
            >
              <span className="w-12 shrink-0 font-semibold tabular-nums" dir="ltr">
                {formatTime(session.starts_at, locale, tenant.time_zone)}
              </span>
              <span aria-hidden="true" className="h-9 w-1 shrink-0 rounded-full" style={{ backgroundColor: color }} />
              <span className="flex min-w-0 flex-1 flex-col gap-1.5">
                <span className={`truncate font-medium ${session.status === "cancelled" ? "text-muted line-through" : ""}`}>
                  {session.service.name}
                </span>
                <span className="text-xs text-muted sm:hidden">
                  {session.status === "cancelled"
                  ? t("schedule.cancelled")
                  : t("schedule.spotsLabel", { booked: session.booked, capacity: session.capacity })}
                </span>
                {session.status !== "cancelled" && (
                  <span aria-hidden="true" className="h-1.5 w-full max-w-48 overflow-hidden rounded-full bg-foreground/8">
                    <span
                      className="block h-full rounded-full transition-[width] duration-700"
                      style={{ width: `${fill * 100}%`, backgroundColor: color }}
                    />
                  </span>
                )}
              </span>
              {/* On wide screens the spots sit at the end; on phones, under the name. */}
              <span className="hidden shrink-0 text-sm text-muted sm:block">
                {session.status === "cancelled"
                  ? t("schedule.cancelled")
                  : t("schedule.spotsLabel", { booked: session.booked, capacity: session.capacity })}
              </span>
              <ArrowRight aria-hidden="true" className="size-4 shrink-0 text-muted opacity-0 transition-all group-hover:opacity-100 rtl:rotate-180" />
            </Link>
          </li>
        );
      })}
    </ul>
  );
  const weekLabel = (bucket: string) => formatDay(bucket, locale, { day: "numeric", month: "numeric" });

  return (
    <main className="enter mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-6 py-10">
      <LiveRefresh />
      {billingNotice && (
        <Link
          href="/settings/billing"
          className="flex items-center gap-3 rounded-2xl border border-warning/50 bg-warning/10 px-4 py-3 text-sm font-medium transition-colors hover:bg-warning/15"
        >
          <CreditCard aria-hidden="true" className="size-5 shrink-0" />
          <span className="flex-1">{billingNotice}</span>
          <ArrowRight aria-hidden="true" className="size-4 rtl:rotate-180" />
        </Link>
      )}
      {usageNotices.map((notice) => (
        <Link
          key={notice}
          href="/settings/billing"
          className="flex items-center gap-3 rounded-2xl border border-warning/50 bg-warning/10 px-4 py-3 text-sm font-medium transition-colors hover:bg-warning/15"
        >
          <Luggage aria-hidden="true" className="size-5 shrink-0" />
          <span className="flex-1">{notice}</span>
          <ArrowRight aria-hidden="true" className="size-4 rtl:rotate-180" />
        </Link>
      ))}
      {setup && (welcome || setup.done < setup.total) && <GettingStartedCard setup={setup} welcome={welcome} business={tenant.name} />}
      <div className="card-accent relative flex flex-wrap items-end justify-between gap-6 overflow-hidden p-0">
        {tenant.cover_url ? (
          // The business's own cover image, under a fade that keeps the text readable.
          // eslint-disable-next-line @next/next/no-img-element -- private image route
          <img src={coverSrc(tenant.cover_url)} alt="" aria-hidden="true" className="absolute inset-0 size-full object-cover" />
        ) : (
          <div aria-hidden="true" className="pointer-events-none absolute -end-16 -top-20 size-64 rounded-full bg-primary/20 blur-3xl" />
        )}
        {tenant.cover_url && (
          <div aria-hidden="true" className="absolute inset-0 bg-gradient-to-t from-surface via-surface/85 to-surface/20 sm:bg-gradient-to-r sm:from-surface sm:via-surface/80 sm:to-transparent rtl:sm:bg-gradient-to-l" />
        )}
        <div className={`relative flex w-full flex-wrap items-end justify-between gap-6 p-6 sm:p-8 ${tenant.cover_url ? "min-h-56 sm:min-h-64" : ""}`}>
        <div className="relative flex flex-col gap-2">
          <p className="text-sm font-medium text-primary">
            {t(`dashboard.greeting.${partOfDay(tenant.time_zone)}`)} ·{" "}
            {formatDay(today, locale, { weekday: "long", day: "numeric", month: "long" })}
          </p>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{t("dashboard.welcome", { name: isolate(tenant.name) })}</h1>
          <p className="text-muted">
            {t("dashboard.yourRole", { role: t(`roles.${tenant.role}`) })} · <span dir="ltr" className="break-all">{me.email}</span>
          </p>
          {canSeeSchedule && (
            <p className="mt-2 flex flex-wrap items-center gap-2 text-sm">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-surface px-3 py-1 font-medium shadow-sm ring-1 ring-border">
                <CalendarCheck aria-hidden="true" className="size-4 text-primary" />
                {t(`terms.${termsOf(tenant.vertical)}.sessionsToday` as "terms.fitness.sessionsToday", { count: todays.filter((s) => s.status !== "cancelled").length })}
              </span>
              <Link href="/schedule" className="inline-flex items-center gap-1 font-medium text-primary underline-offset-4 hover:underline">
                {t("dashboard.openSchedule")}
                <ArrowRight aria-hidden="true" className="size-4 rtl:rotate-180" />
              </Link>
            </p>
          )}
        </div>
        </div>
      </div>

      {mine.length > 0 && (
        <section aria-labelledby="mine-heading" className="flex flex-col gap-3 card-accent p-6">
          <h2 id="mine-heading" className="text-lg font-semibold">
            {t("dashboard.myClassesToday", { count: mine.length })}
          </h2>
          {sessionList(mine)}
        </section>
      )}

      <AttentionPanel context={{ api, scope }} />

      {reports && (
        <section aria-labelledby="kpi-heading" className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 id="kpi-heading" className="text-lg font-semibold">
              {t("dashboard.kpis")}
            </h2>
            <nav aria-label={t("dashboard.period")} className="flex w-full gap-1 rounded-xl border border-border bg-surface p-1 text-sm shadow-sm sm:w-auto">
              {(Object.keys(PERIODS) as Period[]).map((value) => (
                <Link
                  key={value}
                  href={`/dashboard?period=${value}`}
                  aria-current={value === period ? "page" : undefined}
                  className={`flex-1 whitespace-nowrap rounded-lg px-2 py-1 text-center transition-colors sm:flex-none sm:px-3 ${value === period ? "bg-primary text-on-primary shadow-sm" : "hover:bg-foreground/5"}`}
                >
                  {t("dashboard.lastDays", { count: PERIODS[value] })}
                </Link>
              ))}
            </nav>
          </div>
          <ul className="enter-items grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {metrics.map((metric) => {
              const delta =
                metric.value !== null && metric.previous !== null ? metric.value - metric.previous : null;
              const better = delta === null || delta === 0 ? null : delta > 0 === metric.higher_is_better;
              const deltaText =
                delta === null
                  ? null
                  : metric.unit === "percent"
                    ? t("dashboard.points", { value: signed(delta) })
                    : metric.previous
                      ? `${signed((delta / metric.previous) * 100)}%`
                      : null;
              const Icon = TILE_ICONS[metric.key as keyof typeof TILE_ICONS] ?? Gauge;
              const DeltaIcon = delta! > 0 ? ArrowUpRight : delta! < 0 ? ArrowDownRight : Minus;
              return (
                <li key={metric.key} className="card card-hover flex flex-col gap-3 p-5">
                  <span className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-muted">{t(`metrics.${metric.key}`)}</span>
                    <span className="icon-tile size-9">
                      <Icon aria-hidden="true" className="size-[18px]" />
                    </span>
                  </span>
                  <span className="text-3xl font-bold tracking-tight">
                    {metric.value === null ? (
                      show(metric, null)
                    ) : (
                      <CountUp
                        value={metric.value}
                        kind={metric.unit === "money" ? "money" : metric.unit === "percent" ? "percent" : "count"}
                        currency={tenant.currency}
                      />
                    )}
                  </span>
                  {deltaText && (
                    <span className="flex flex-wrap items-center gap-1.5 text-sm">
                      <span
                        className={`inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 font-semibold ${
                          better === null ? "bg-foreground/8" : better ? "bg-success/12" : "bg-danger/12"
                        }`}
                      >
                        <DeltaIcon
                          aria-hidden="true"
                          className={`size-3.5 ${better === null ? "text-muted" : better ? "text-success" : "text-danger"}`}
                        />
                        <span>{deltaText}</span>
                      </span>
                      <span className="text-muted">{t("dashboard.vsPrevious")}</span>
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
        <section className="card grid gap-8 p-6 lg:grid-cols-2">
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

      {canSeeSchedule && <section aria-labelledby="today-heading" className="card flex flex-col gap-3 p-6">
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
