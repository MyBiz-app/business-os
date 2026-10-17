import { dayOf, formatTime, localValue, monthStart, todayIn } from "@business-os/i18n/dates";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import { BRAND } from "@business-os/i18n/brand";

import { BackLink } from "@/components/back-link";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { formatDay } from "@/lib/dates";
import { unwrap } from "@/lib/api";
import { hm } from "@/lib/time-clock";
import { getBranches, getTenantFor } from "@/lib/tenant";

import { ApprovalForm, EntryForm, NewEntryForm } from "./entry-forms";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("timeClock");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** One person's month: totals by pay rate, hours per day, and every entry to fix. */
export default async function PersonTimeClockPage({ params, searchParams }: PageProps<"/team/time-clock/[userId]">) {
  const { userId } = await params;
  const query = await searchParams;
  const t = await getTranslations("timeClock");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("time.approve");
  const month = typeof query.month === "string" && /^\d{4}-\d{2}$/.test(query.month) ? query.month : monthStart(todayIn(tenant.time_zone)).slice(0, 7);
  const [detail, rules, branches] = await Promise.all([
    api.GET("/time-clock/people/{user_id}", { params: { ...scope, path: { user_id: userId }, query: { month } } }).then(unwrap),
    api.GET("/time-clock/rules", { params: scope }).then(unwrap),
    getBranches(),
  ]);
  const zone = tenant.time_zone;
  const worked = detail.worked;
  const rows: [string, number][] = [
    [t("regular"), worked.regular],
    [t("tier1", { percent: rules.tier1_percent }), worked.tier1],
    [t("tier2", { percent: rules.tier2_percent }), worked.tier2],
    [t("restDay", { percent: rules.rest_day_percent }), worked.rest_day],
    [t("total"), worked.total],
    [t("weighted"), worked.weighted],
  ];
  const stamp = (instant: string) => `${formatDay(dayOf(instant, zone), locale, { weekday: "short", day: "numeric", month: "short" })} ${formatTime(instant, locale, zone)}`;

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href={`/team/time-clock?month=${month}`} label={t("title")} />
      <PageHeader title={detail.user_name} description={`${month} · ${t("planned")}: ${hm(detail.planned_hours)}`} />

      <section className="card flex flex-col gap-3 p-5" aria-labelledby="totals-heading">
        <h2 id="totals-heading" className="text-lg font-semibold">
          {t("worked")}
        </h2>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
          {rows.map(([label, value]) => (
            <div key={label} className="flex flex-col">
              <dt className="text-muted">{label}</dt>
              <dd className="font-medium tabular-nums">{hm(value)}</dd>
            </div>
          ))}
        </dl>
        <ApprovalForm userId={userId} month={month} approved={detail.approved} />
        {detail.approved && <p className="text-sm text-muted">{t("locked")}</p>}
      </section>

      <section className="flex flex-col gap-3" aria-labelledby="entries-heading">
        <h2 id="entries-heading" className="text-lg font-semibold">
          {t("entries")}
        </h2>
        {detail.entries.length === 0 && <p className="card p-5 text-sm text-muted">{t("empty")}</p>}
        {detail.entries.map((entry) => (
          <article key={entry.id} className="card flex flex-col gap-3 p-5">
            <p className="text-sm">
              <span className="font-medium">
                {stamp(entry.clock_in)} - {entry.clock_out ? stamp(entry.clock_out) : t("running")}
              </span>
              <span className="block text-muted" dir="auto">
                {entry.location_name} · {entry.source === "manual" ? t("manual") : t("clock")}
                {entry.correction_reason ? ` · ${entry.correction_reason}` : ""}
              </span>
            </p>
            {!detail.approved && (
              <EntryForm
                entryId={entry.id}
                userId={userId}
                clockIn={localValue(entry.clock_in, zone)}
                clockOut={entry.clock_out ? localValue(entry.clock_out, zone) : ""}
              />
            )}
          </article>
        ))}
      </section>

      {!detail.approved && (
        <section className="card flex flex-col gap-3 p-5" aria-labelledby="add-heading">
          <h2 id="add-heading" className="text-lg font-semibold">
            {t("addEntry")}
          </h2>
          <NewEntryForm userId={userId} branches={branches.map((b) => ({ value: b.id, label: b.name }))} />
        </section>
      )}
    </Container>
  );
}
