import { addMonths, monthStart, todayIn } from "@business-os/i18n/dates";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { BackLink } from "@/components/back-link";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { unwrap } from "@/lib/api";
import { hm } from "@/lib/time-clock";
import { getTenantFor } from "@/lib/tenant";

import { RulesForm } from "./rules-form";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("timeClock");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** The month's hours per person: planned against clocked, missing shifts, overtime and approval. */
export default async function TimeClockPage({ searchParams }: PageProps<"/team/time-clock">) {
  const t = await getTranslations("timeClock");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("time.approve");
  const query = await searchParams;
  const requested = typeof query.month === "string" && /^\d{4}-\d{2}$/.test(query.month) ? `${query.month}-01` : null;
  const first = requested ?? monthStart(todayIn(tenant.time_zone));
  const month = first.slice(0, 7);
  const [overview, rules] = await Promise.all([
    api.GET("/time-clock/month", { params: { ...scope, query: { month } } }).then(unwrap),
    api.GET("/time-clock/rules", { params: scope }).then(unwrap),
  ]);
  const label = new Intl.DateTimeFormat(locale, { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${first}T00:00:00Z`));
  const step = (months: number) => `/team/time-clock?month=${addMonths(first, months).slice(0, 7)}`;
  const canEditRules = tenant.permissions.includes("business.settings");

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/team" label={t("back")} />
      <PageHeader title={t("title")} description={t("subtitle")} />
      <nav aria-label={t("month")} className="flex items-center gap-3">
        <Link scroll={false} href={step(-1)} className="btn-secondary px-3 py-2 text-sm">
          {t("previous")}
        </Link>
        <h2 className="text-lg font-semibold">{label}</h2>
        <Link scroll={false} href={step(1)} className="btn-secondary px-3 py-2 text-sm">
          {t("next")}
        </Link>
      </nav>

      {overview.people.length === 0 ? (
        <p className="card p-5 text-sm text-muted">{t("empty")}</p>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[40rem] text-sm">
            <thead className="text-start text-muted">
              <tr>
                <th scope="col" className="p-3 text-start font-medium">{t("person")}</th>
                <th scope="col" className="p-3 text-start font-medium">{t("planned")}</th>
                <th scope="col" className="p-3 text-start font-medium">{t("worked")}</th>
                <th scope="col" className="p-3 text-start font-medium">{t("overtime")}</th>
                <th scope="col" className="p-3 text-start font-medium">{t("missing")}</th>
                <th scope="col" className="p-3 text-start font-medium">{t("status")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {overview.people.map((person) => (
                <tr key={person.user_id}>
                  <th scope="row" className="p-3 text-start font-medium">
                    <Link href={`/team/time-clock/${person.user_id}?month=${month}`} dir="auto" className="underline-offset-2 hover:underline">
                      {person.user_name}
                    </Link>
                  </th>
                  <td className="p-3 tabular-nums">{hm(person.planned_hours)}</td>
                  <td className="p-3 tabular-nums">{hm(person.worked.total)}</td>
                  <td className="p-3 tabular-nums">{hm(person.worked.tier1 + person.worked.tier2 + person.worked.rest_day)}</td>
                  <td className={`p-3 tabular-nums ${person.missing_shifts > 0 ? "text-warning" : ""}`}>{person.missing_shifts}</td>
                  <td className="p-3">
                    {person.approved ? t("approved") : person.open_entries > 0 ? t("open_entries") : t("pending")}
                    {person.corrections > 0 && <span className="block text-xs text-muted">{t("corrections", { count: person.corrections })}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <section aria-labelledby="rules-heading" className="card flex flex-col gap-4 p-5">
        <h2 id="rules-heading" className="text-lg font-semibold">
          {t("rules.title")}
        </h2>
        <p className="text-sm text-muted">{t("rules.hint")}</p>
        <RulesForm rules={rules} canEdit={canEditRules} locale={locale} />
      </section>
    </Container>
  );
}
