import type { components } from "@business-os/api-client";
import { Search } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import { Suspense } from "react";

import { NeedsYou } from "./needs-you";
import { NewMenu } from "./new-menu";
import { RotatingCard } from "./rotating-card";
import { TodayCard } from "./today-card";
import { usageWarnings } from "@business-os/i18n/usage";
import { businessTerms } from "@/lib/verticals";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { LiveRefresh } from "@/components/live-refresh";
import { CountUp } from "@/components/motion/count-up";
import { ButtonLink } from "@/components/ui/button";
import { StatTile, type Trend } from "@/components/ui/stat-tile";
import { unwrap } from "@/lib/api";
import { isolate } from "@/lib/bidi";
import { formatDay, todayIn } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { canManageSettings, canReadReports, canManageBookings, canWriteClients, canWriteSchedule } from "@/lib/permissions";
import { resolveRange } from "@/lib/range";
import { isSolo, SOLO_ATTENTION, SOLO_DASHBOARD_TILES } from "@/lib/solo";
import { getBranches, getTenant } from "@/lib/tenant";

type MetricValue = components["schemas"]["MetricValue"];

const PRESETS = [30] as const;
/** The four numbers of the morning; every other number lives in Reports. */
const TILES = ["revenue", "active_clients", "attendance", "new_clients"] as const;

/** The part of the day in the business's time zone, for the greeting. */
function partOfDay(timeZone: string): "morning" | "afternoon" | "evening" | "night" {
  const hour = Number(new Intl.DateTimeFormat("en-GB", { hour: "numeric", hourCycle: "h23", timeZone }).format(new Date()));
  return hour < 5 ? "night" : hour < 12 ? "morning" : hour < 17 ? "afternoon" : hour < 22 ? "evening" : "night";
}

/** "My Day": the page an owner opens in the morning. Six zones, all in the first screen on a
 * desktop: the greeting with "+ New" and search, what needs you, today's timeline, four numbers
 * and one rotating card. An employee gets "my shift and my classes today". */
export default async function DashboardPage({ searchParams }: PageProps<"/dashboard">) {
  const t = await getTranslations();
  const locale = await getLocale();
  const { me, tenant, api, scope } = await getTenant();
  const query = await searchParams;
  const today = todayIn(tenant.time_zone);
  // Completed days only, so the comparison with the previous period is fair.
  const { start, end, days } = resolveRange({}, today, { presets: PRESETS, fallback: 30 });
  const reports = canReadReports(tenant);
  const solo = isSolo(tenant);
  const tiles = solo ? SOLO_DASHBOARD_TILES : TILES;
  const branches = reports && !solo ? await getBranches() : [];
  const canSeeSchedule = tenant.permissions.includes("schedule.read");
  const manager = canManageSettings(tenant);
  const welcome = query.welcome === "1";

  const [todays, shifts, metrics, billing, setup, websiteOffer] = await Promise.all([
    canSeeSchedule ? api.GET("/sessions", { params: { ...scope, query: { start: today, days: 1 } } }).then(unwrap) : [],
    // An employee's own shift today.
    !reports && !solo ? api.GET("/shifts", { params: { ...scope, query: { start: today, days: 1, user_id: me.id } } }).then((r) => r.data ?? []) : [],
    reports ? api.GET("/metrics", { params: { ...scope, query: { start, end, keys: [...tiles] } } }).then(unwrap) : [],
    // The MyBiz subscription: remind whoever manages settings before the trial ends or when an invoice is unpaid.
    manager ? api.GET("/billing", { params: scope }).then((r) => r.data) : undefined,
    // The first-steps checklist, for whoever sets the business up, until it's all done.
    manager ? api.GET("/tenants/current/getting-started", { params: scope }).then((r) => r.data) : undefined,
    // Once, after the first 30 days, for a business without a website (the person can close it).
    manager ? api.GET("/website/offer-card", { params: scope }).then((r) => r.data) : undefined,
  ]);

  const billingNotice = !billing
    ? null
    : billing.balance_due > 0
      ? { text: t("billing.dashboardDue", { amount: formatMoney(billing.balance_due, billing.estimate.currency, locale) }), due: true }
      : billing.in_trial && !billing.payment_method && billing.trial_days_left <= 7
        ? { text: t("billing.dashboardTrial", { days: billing.trial_days_left }), due: false }
        : null;
  // Space and messages: warn from 80% of the bundle. Messages keep going over it; new files stop.
  const usageNotices = billing ? usageWarnings(billing.usage).map(({ key, percent }) => t(`billing.usage.${key}`, { percent })) : [];

  const number = new Intl.NumberFormat(locale);
  const signed = (value: number) => {
    const rounded = Math.round(value) || 0;
    return `${rounded > 0 ? "+" : ""}${number.format(rounded)}`;
  };
  /** The small arrow under a number: the change against the previous period. */
  const trendOf = (metric: MetricValue): Trend | undefined => {
    if (metric.value === null || metric.previous === null) return undefined;
    const delta = metric.value - metric.previous;
    const label = metric.unit === "percent" ? t("dashboard.points", { value: signed(delta) }) : metric.previous ? `${signed((delta / metric.previous) * 100)}%` : null;
    if (label === null) return undefined;
    return {
      direction: delta > 0 ? "up" : delta < 0 ? "down" : "flat",
      label,
      tone: delta === 0 ? "neutral" : delta > 0 === metric.higher_is_better ? "good" : "bad",
    };
  };
  // Where each tile leads: the same period, already filtered to what the number counts.
  const tileHref = (key: string) => {
    const span = new URLSearchParams({ from: start, to: end });
    switch (key) {
      case "revenue":
        return `/sales?${span}`;
      case "active_clients":
        return "/clients?status=active";
      case "new_clients":
        return `/clients?${new URLSearchParams({ joined_from: start, joined_to: end })}`;
      case "attendance":
        return `/schedule?${new URLSearchParams({ view: "month", date: end })}`;
      default:
        return "/reports";
    }
  };

  const term = businessTerms(t, tenant, locale);
  const mine = todays.filter((session) => session.instructor_user_id === me.id);
  // An employee (no reports) sees their own classes; everyone else sees the whole day.
  const timeline = reports || solo ? todays : mine;
  const timelineTitle = reports || solo ? t("dashboard.today") : t("dashboard.myClassesToday", { count: mine.length });
  const hello = t(`dashboard.greeting.${partOfDay(tenant.time_zone)}`);
  const firstName = me.full_name?.trim().split(/\s+/)[0];

  const newItems = [
    canWriteClients(tenant) && { key: "client", label: term("addClient"), href: "/clients/new" },
    canWriteClients(tenant) && tenant.modules.includes("crm") && { key: "lead", label: t("dashboard.newLead"), href: "/leads/new" },
    canWriteSchedule(tenant) && !solo && { key: "session", label: term("newSession"), href: "/schedule/new" },
    canManageBookings(tenant) && { key: "appointment", label: t("dashboard.newAppointment"), href: "/schedule/appointment" },
  ].filter((item) => item !== false);

  // An employee's home is their own shift and classes; what needs the owner is the owner's.
  const showNeeds = reports || solo;
  const needsHref = (all: boolean) => (all ? "/dashboard?needs=all" : "/dashboard");
  const showMap = reports && !solo && branches.length > 1;

  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-5 py-6 sm:py-8">
      <LiveRefresh />
      <PageHeader
        title={firstName ? t("dashboard.hello", { greeting: hello, name: isolate(firstName) }) : hello}
        description={formatDay(today, locale, { weekday: "long", day: "numeric", month: "long" })}
        actions={
          <>
            {tenant.permissions.includes("clients.read") && (
              <form role="search" action="/clients" className="relative sm:w-64">
                <Search aria-hidden="true" className="pointer-events-none absolute inset-y-0 start-3 my-auto size-4 text-muted" />
                <input type="search" name="q" aria-label={term("searchClients")} placeholder={term("searchClients")} className="control w-full py-2 ps-9 pe-3" />
              </form>
            )}
            {newItems.length > 0 && <NewMenu label={t("dashboard.new")} items={newItems as { key: string; label: string; href: string }[]} />}
          </>
        }
      />

      <div className={`grid items-start gap-5 ${showNeeds ? "lg:grid-cols-2" : "max-w-3xl"}`}>
        {showNeeds && (
          <Suspense fallback={null}>
            <NeedsYou
              context={{ api, scope, tenant }}
              only={solo ? SOLO_ATTENTION : undefined}
              billingNotice={billingNotice}
              usageNotices={usageNotices}
              showAll={query.needs === "all"}
              showAllHref={needsHref(true)}
              collapseHref={needsHref(false)}
            />
          </Suspense>
        )}
        {canSeeSchedule && (
          <TodayCard
            title={timelineTitle}
            sessions={timeline}
            shifts={shifts}
            userId={me.id}
            timeZone={tenant.time_zone}
            emptyText={t("dashboard.emptyToday")}
            scheduleHref={tenant.permissions.includes("schedule.read") ? "/schedule" : null}
          />
        )}
      </div>

      {reports && (
        <section aria-labelledby="kpi-heading" className="flex flex-col gap-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 id="kpi-heading" className="text-lg font-semibold">
              {t("dashboard.kpis")}
              <span className="ms-2 text-sm font-normal text-muted">{t("dashboard.lastDays", { count: days })}</span>
            </h2>
            <ButtonLink href={`/reports?${new URLSearchParams({ from: start, to: end })}`} variant="quiet">
              {t("dashboard.allReports")}
            </ButtonLink>
          </div>
          <ul className={`enter-items grid grid-cols-2 gap-3 ${solo ? "lg:grid-cols-3" : "lg:grid-cols-4"}`}>
            {metrics.map((metric) => (
              <li key={metric.key}>
                <StatTile
                  label={t(`metrics.${metric.key}`)}
                  href={tileHref(metric.key)}
                  trend={trendOf(metric)}
                  hint={trendOf(metric) ? t("dashboard.vsPrevious") : undefined}
                  value={
                    metric.value === null ? (
                      "-"
                    ) : (
                      <CountUp value={metric.value} kind={metric.unit === "money" ? "money" : metric.unit === "percent" ? "percent" : "count"} currency={tenant.currency} />
                    )
                  }
                />
              </li>
            ))}
          </ul>
        </section>
      )}

      <Suspense fallback={null}>
        <RotatingCard context={{ api, scope, tenant }} setup={setup} welcome={welcome} websiteOffer={!!websiteOffer?.show} showMap={showMap} />
      </Suspense>
    </Container>
  );
}
