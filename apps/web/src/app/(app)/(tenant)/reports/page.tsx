import type { components } from "@business-os/api-client";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Pill } from "@/components/pill";
import { ReviewsSummary } from "@/components/reviews-summary";
import { unwrap } from "@/lib/api";
import { addDays, formatDay, todayIn } from "@/lib/dates";
import { getTenantFor } from "@/lib/tenant";
import { ScrollRegion } from "@/components/scroll-region";

type Row = components["schemas"]["BreakdownItem"];

const PERIODS = { "30": 30, "90": 90 } as const;
type Period = keyof typeof PERIODS;
const AT_RISK_DAYS = 14;
const SHOWN = 10; // members listed before "show all"
// A Monday, to name ISO weekdays (1 = Monday) in the user's language.
const MONDAY = "2024-01-01";

export default async function ReportsPage({ searchParams }: PageProps<"/reports">) {
  const t = await getTranslations("reports");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("reports.read");
  const query = await searchParams;
  const period: Period = query.period === "90" ? "90" : "30";
  const end = addDays(todayIn(tenant.time_zone), -1);
  const start = addDays(end, -(PERIODS[period] - 1));
  const range = { start, end };

  const [byService, byInstructor, bySlot, atRisk, reviews] = await Promise.all([
    api.GET("/metrics/breakdown/{dimension}", { params: { ...scope, path: { dimension: "service" }, query: range } }).then(unwrap),
    api.GET("/metrics/breakdown/{dimension}", { params: { ...scope, path: { dimension: "instructor" }, query: range } }).then(unwrap),
    api.GET("/metrics/breakdown/{dimension}", { params: { ...scope, path: { dimension: "time_slot" }, query: range } }).then(unwrap),
    api.GET("/metrics/members-at-risk", { params: { ...scope, query: { days: AT_RISK_DAYS } } }).then(unwrap),
    api.GET("/reviews", { params: { ...scope, query: { days: PERIODS[period] } } }).then(unwrap),
  ]);
  const tReviews = await getTranslations("reviews");

  const number = new Intl.NumberFormat(locale);
  const percent = (value: number | null) => (value === null ? "—" : `${number.format(Math.round(value))}%`);
  const slotLabel = (key: string) => {
    const [weekday, hour] = key.split("-").map(Number);
    const day = formatDay(addDays(MONDAY, weekday - 1), locale, { weekday: "long" });
    return `${day} ${String(hour).padStart(2, "0")}:00`;
  };
  const dateLabel = (day: string) => formatDay(day, locale, { day: "numeric", month: "short" });
  // Busiest slots first, so the table answers "when do people come".
  const slots = [...bySlot].sort((a, b) => b.attended - a.attended).slice(0, 10);

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

  const table = (id: string, title: string, nameHeader: string, rows: Row[], name: (row: Row) => string) => (
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
                    <bdi>{name(row)}</bdi>
                  </th>
                  <td className="py-2 pe-4 text-end tabular-nums">{number.format(row.sessions)}</td>
                  <td className="py-2 pe-4 text-end tabular-nums">{number.format(row.attended)}</td>
                  <td className="py-2 pe-4 text-end tabular-nums">{percent(row.occupancy)}</td>
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
    <main className="enter mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold">{t("title")}</h1>
          <p className="text-muted">{t("intro")}</p>
        </div>
        <nav aria-label={t("period")} className="flex gap-1 rounded-xl border border-border bg-surface p-1 text-sm shadow-sm">
          {(Object.keys(PERIODS) as Period[]).map((value) => (
            <Link
              key={value}
              href={`/reports?period=${value}`}
              aria-current={value === period ? "page" : undefined}
              className={`whitespace-nowrap rounded-lg px-3 py-1 transition-colors ${value === period ? "bg-primary text-on-primary shadow-sm" : "hover:bg-foreground/5"}`}
            >
              {t("lastDays", { count: PERIODS[value] })}
            </Link>
          ))}
        </nav>
      </div>

      <ReviewsSummary
        summary={reviews}
        locale={locale}
        timeZone={tenant.time_zone}
        title={tReviews("title", { count: PERIODS[period] })}
      />
      {table("by-service", t("byService"), t("service"), byService, (row) => row.label ?? "—")}
      {table("by-instructor", t("byInstructor"), t("instructor"), byInstructor, (row) => row.label ?? t("noInstructor"))}
      {table("by-slot", t("bySlot"), t("slot"), slots, (row) => slotLabel(row.key))}
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
          <details>
            <summary className="cursor-pointer text-sm text-primary">{t("showAll", { count: atRisk.length })}</summary>
            <ul className="mt-2 flex flex-col divide-y divide-border">{atRisk.slice(SHOWN).map(memberRow)}</ul>
          </details>
        )}
      </section>

    </main>
  );
}
