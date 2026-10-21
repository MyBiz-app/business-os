import type { components } from "@business-os/api-client";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { PendingArea, PeriodPicker, PeriodProvider } from "@/components/period-picker";
import { Pill } from "@/components/pill";
import { ReviewsSummary } from "@/components/reviews-summary";
import { unwrap } from "@/lib/api";
import { formatDay, todayIn } from "@/lib/dates";
import { resolveRange } from "@/lib/range";
import { formatMoney } from "@/lib/money";
import { getTenantFor } from "@/lib/tenant";
import { ScrollRegion } from "@/components/scroll-region";

import { BranchComparison } from "./branch-comparison";
import { BranchLink } from "./branch-link";
import { BusyHours } from "./busy-hours";
import { CollapsibleSection } from "@/components/ui/collapsible-section";

type Row = components["schemas"]["BreakdownItem"];

const PRESETS = [7, 30, 90] as const;
const AT_RISK_DAYS = 14;
const SHOWN = 10; // members listed before "show all"
const COMPARED = ["revenue", "new_clients", "active_clients", "plans_sold", "attendance", "occupancy"] as const;

export default async function ReportsPage({ searchParams }: PageProps<"/reports">) {
  const t = await getTranslations("reports");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("reports.read");
  const query = await searchParams;
  const today = todayIn(tenant.time_zone);
  const chosen = resolveRange(query, today, { presets: PRESETS, fallback: 30 });
  const { start, end } = chosen;
  const range = { start, end };
  const excludeStaff = query.staff === "exclude";
  const filtered = { ...range, exclude_staff: excludeStaff };

  const [byService, byInstructor, bySlot, byBranch, atRisk, reviews, courts, compared] = await Promise.all([
    api.GET("/metrics/breakdown/{dimension}", { params: { ...scope, path: { dimension: "service" }, query: filtered } }).then(unwrap),
    api.GET("/metrics/breakdown/{dimension}", { params: { ...scope, path: { dimension: "instructor" }, query: filtered } }).then(unwrap),
    api.GET("/metrics/breakdown/{dimension}", { params: { ...scope, path: { dimension: "time_slot" }, query: filtered } }).then(unwrap),
    api.GET("/metrics/breakdown/{dimension}", { params: { ...scope, path: { dimension: "branch" }, query: filtered } }).then(unwrap),
    api.GET("/metrics/members-at-risk", { params: { ...scope, query: { days: AT_RISK_DAYS, exclude_staff: excludeStaff } } }).then(unwrap),
    api.GET("/reviews", { params: { ...scope, query: { days: chosen.days } } }).then(unwrap),
    api.GET("/reports/resources", { params: { ...scope, query: range } }).then(unwrap),
    // Branch by branch, across the person's branches (not just the one picked in the menu).
    api
      .GET("/metrics/branches", {
        params: { header: { "X-Tenant-Id": scope.header["X-Tenant-Id"] }, query: { ...range, keys: [...COMPARED], exclude_staff: excludeStaff } },
      })
      .then((r) => r.data ?? []),
  ]);
  const tReviews = await getTranslations("reviews");

  const number = new Intl.NumberFormat(locale);
  const percent = (value: number | null) => (value === null ? "-" : `${number.format(Math.round(value))}%`);
  const dateLabel = (day: string) => formatDay(day, locale, { day: "numeric", month: "short" });

  // From a row to the schedule of the same period's last month, filtered to that service or person.
  const scheduleLink = (filter: "service" | "instructor", row: Row, text: string) =>
    row.key ? (
      <Link
        href={`/schedule?${new URLSearchParams({ view: "month", date: end, [filter]: row.key })}`}
        className="underline-offset-4 hover:text-primary-ink hover:underline"
      >
        <bdi>{text}</bdi>
      </Link>
    ) : null;
  const byServiceRows = query.sort === "occupancy" ? [...byService].sort((a, b) => (b.occupancy ?? -1) - (a.occupancy ?? -1)) : byService;
  const memberRow = (member: (typeof atRisk)[number]) => (
    <li key={member.client_id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
      <Link href={`/clients/${member.client_id}`} dir="auto" className="font-medium underline-offset-4 hover:underline">
        {member.name}
      </Link>
      <span className="flex flex-wrap items-center gap-2 text-sm text-muted">
        <Pill tone={member.reason === "inactive" ? "danger" : "primary"}>{t(`reasons.${member.reason}`)}</Pill>
        {member.last_visit ? t("lastVisit", { date: dateLabel(member.last_visit) }) : t("neverVisited")}
        {member.plan_ends_on && ` · ${t("planEnds", { date: dateLabel(member.plan_ends_on) })}`}
      </span>
    </li>
  );

  const table = (id: string, title: string, nameHeader: string, rows: Row[], name: (row: Row) => string, link?: (row: Row) => React.ReactNode) => (
    <section aria-labelledby={id} className="flex flex-col gap-3 card p-6">
      <h2 id={id} className="text-lg font-semibold">
        {title}
      </h2>
      {rows.length === 0 ? (
        <p className="text-sm text-muted">{t("noSessions")}</p>
      ) : (
        <ScrollRegion labelledBy={id}>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-start text-muted">
                <th scope="col" className="py-2 pe-4 text-start font-medium">{nameHeader}</th>
                <th scope="col" className="py-2 pe-4 text-end font-medium">{t("sessions")}</th>
                <th scope="col" className="py-2 pe-4 text-end font-medium">{t("attended")}</th>
                <th scope="col" className="py-2 pe-4 text-end font-medium">{t("occupancy")}</th>
                <th scope="col" className="py-2 text-end font-medium">{t("noShowRate")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.key} className="border-b border-border last:border-0">
                  <th scope="row" className="py-2 pe-4 text-start font-medium">
                    {link?.(row) ?? <bdi>{name(row)}</bdi>}
                  </th>
                  <td className="py-2 pe-4 text-end tabular-nums">{number.format(row.sessions)}</td>
                  <td className="py-2 pe-4 text-end tabular-nums">{number.format(row.attended)}</td>
                  <td className="py-2 pe-4">
                    <span className="flex items-center justify-end gap-2 tabular-nums">
                      {row.occupancy !== null && (
                        <span aria-hidden="true" className="hidden h-1.5 w-20 overflow-hidden rounded-full bg-foreground/8 sm:block">
                          <span className="block h-full rounded-full bg-primary" style={{ inlineSize: `${Math.min(100, row.occupancy)}%` }} />
                        </span>
                      )}
                      {percent(row.occupancy)}
                    </span>
                  </td>
                  <td className="py-2 text-end tabular-nums">{percent(row.no_show_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      )}
    </section>
  );

  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PeriodProvider>
      <PageHeader
        title={t("title")}
        description={t("intro")}
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <Link
              scroll={false}
              href={{ pathname: "/reports", query: { ...query, staff: excludeStaff ? undefined : "exclude" } }}
              aria-current={excludeStaff ? "true" : undefined}
              className={excludeStaff ? "btn-primary px-3 py-1.5 text-sm" : "btn-secondary px-3 py-1.5 text-sm"}
            >
              {t("withoutStaff")}
            </Link>
            <PeriodPicker presets={PRESETS} value={chosen.key} from={start} to={end} today={today} reset={["sort"]} />
          </div>
        }
      />

      <PendingArea className="flex flex-col gap-6">
      {compared.length > 1 && <BranchComparison rows={compared} currency={tenant.currency} locale={locale} />}
      {/* Comparing branches matters once there is more than one (and none is selected). */}
      {byBranch.length > 1 && table("by-branch", t("byBranch"), t("branch"), byBranch, (row) => row.label || t("noBranch"), (row) =>
        row.key ? <BranchLink id={row.key}>{row.label}</BranchLink> : null,
      )}
      {/* Side by side on a wide screen; stacked on a laptop or phone. */}
      <div className="grid items-start gap-6 2xl:grid-cols-2">
        {table("by-service", t("byService"), t("service"), byServiceRows, (row) => row.label ?? "-", (row) => scheduleLink("service", row, row.label ?? "-"))}
        {table("by-instructor", t("byInstructor"), t("instructor"), byInstructor, (row) => row.label ?? t("noInstructor"), (row) =>
          scheduleLink("instructor", row, row.label ?? t("noInstructor")),
        )}
      </div>
      {bySlot.length > 0 && <BusyHours rows={bySlot} locale={locale} />}
      {/* Courts and rooms rented by the hour: how much of their open time was reserved. */}
      {courts.length > 0 && (
        <section aria-labelledby="by-court" className="flex flex-col gap-3 card p-6">
          <h2 id="by-court" className="text-lg font-semibold">
            {t("byCourt")}
          </h2>
          <ScrollRegion labelledBy="by-court">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-start text-muted">
                  <th scope="col" className="py-2 pe-4 text-start font-medium">{t("court")}</th>
                  <th scope="col" className="py-2 pe-4 text-end font-medium">{t("reservations")}</th>
                  <th scope="col" className="py-2 pe-4 text-end font-medium">{t("reservedHours")}</th>
                  <th scope="col" className="py-2 pe-4 text-end font-medium">{t("occupancy")}</th>
                  <th scope="col" className="py-2 text-end font-medium">{t("courtRevenue")}</th>
                </tr>
              </thead>
              <tbody>
                {courts.map((row) => (
                  <tr key={row.room_id} className="border-b border-border last:border-0">
                    <th scope="row" className="py-2 pe-4 text-start font-medium">
                      <bdi>{row.room_name}</bdi>
                      <span className="block text-xs font-normal text-muted">
                        <bdi>{row.location_name}</bdi>
                      </span>
                    </th>
                    <td className="py-2 pe-4 text-end tabular-nums">{number.format(row.reservations)}</td>
                    <td className="py-2 pe-4 text-end tabular-nums">
                      {t("hoursOf", { reserved: number.format(row.reserved_hours), open: number.format(row.open_hours) })}
                    </td>
                    <td className="py-2 pe-4">
                      <span className="flex items-center justify-end gap-2 tabular-nums">
                        {row.occupancy_percent !== null && (
                          <span aria-hidden="true" className="hidden h-1.5 w-20 overflow-hidden rounded-full bg-foreground/8 sm:block">
                            <span className="block h-full rounded-full bg-primary" style={{ inlineSize: `${Math.min(100, row.occupancy_percent)}%` }} />
                          </span>
                        )}
                        {percent(row.occupancy_percent)}
                      </span>
                    </td>
                    <td className="py-2 text-end tabular-nums">{formatMoney(row.revenue, row.currency, locale)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
        </section>
      )}
      <section aria-labelledby="at-risk-heading" className="flex flex-col gap-3 card p-6">
        <div className="flex flex-col gap-1">
          <h2 id="at-risk-heading" className="text-lg font-semibold">
            {t("atRisk", { count: atRisk.length })}
          </h2>
          <p className="text-sm text-muted">{t("atRiskHint", { days: AT_RISK_DAYS })}</p>
        </div>
        {atRisk.length === 0 ? (
          <p className="text-sm text-muted">{t("atRiskNone")}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {atRisk.slice(0, SHOWN).map(memberRow)}
          </ul>
        )}
        {atRisk.length > SHOWN && (
          <CollapsibleSection variant="inline" title={t("showAll", { count: atRisk.length })}>
            <ul className="flex flex-col divide-y divide-border">{atRisk.slice(SHOWN).map(memberRow)}</ul>
          </CollapsibleSection>
        )}
      </section>
      {/* Reviews come last: the numbers people act on every day go first. */}
      <ReviewsSummary
        summary={reviews}
        locale={locale}
        timeZone={tenant.time_zone}
        title={tReviews("title", { count: chosen.days })}
      />
      </PendingArea>
      </PeriodProvider>
    </Container>
  );
}
