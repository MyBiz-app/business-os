import { formatMoney } from "@business-os/i18n/money";
import { BRAND } from "@business-os/i18n/brand";
import { Download } from "lucide-react";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { BackLink } from "@/components/back-link";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("payRun.annual");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** The tax year's approved months per person, the data behind Form 106 (owner only). */
export default async function AnnualPayrollPage({ searchParams }: PageProps<"/team/payroll/annual">) {
  const t = await getTranslations("payRun.annual");
  const locale = await getLocale();
  const { api, scope } = await getTenantFor("payroll.approve");
  const query = await searchParams;
  const current = new Date().getUTCFullYear();
  const requested = typeof query.year === "string" && /^\d{4}$/.test(query.year) ? Number(query.year) : current;
  const year = Math.min(2100, Math.max(2000, requested));
  const summary = unwrap(await api.GET("/payroll/annual/{year}", { params: { ...scope, path: { year } } }));
  const money = (amount: number) => formatMoney(amount, summary.currency, locale);
  const columns = ["months", "gross", "tax", "ni", "health", "pension", "net", "employer"] as const;

  return (
    <Container as="main" size="wide" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/team/payroll" label={t("back")} />
      <PageHeader title={t("title")} description={t("subtitle")} />
      <nav aria-label={t("yearNav")} className="flex flex-wrap items-center gap-3">
        <Link scroll={false} href={`/team/payroll/annual?year=${year - 1}`} className="btn-secondary px-3 py-2 text-sm">
          {t("previous")}
        </Link>
        <h2 className="text-lg font-semibold tabular-nums">{year}</h2>
        <Link scroll={false} href={`/team/payroll/annual?year=${year + 1}`} className="btn-secondary px-3 py-2 text-sm">
          {t("next")}
        </Link>
        <a href={`/team/payroll/annual/export?year=${year}&format=xlsx`} download className="btn-secondary ms-auto px-3 py-2 text-sm">
          <Download aria-hidden="true" className="size-4" />
          {t("exportXlsx")}
        </a>
        <a href={`/team/payroll/annual/export?year=${year}&format=csv`} download className="btn-ghost px-3 py-2 text-sm">
          {t("exportCsv")}
        </a>
      </nav>
      {summary.people.length === 0 ? (
        <p className="card p-6 text-sm text-muted">{t("empty")}</p>
      ) : (
        <>
          {summary.draft && <p className="text-sm text-muted">{t("draft")}</p>}
          <div className="card overflow-x-auto">
            <table className="w-full min-w-[48rem] text-sm">
              <thead>
                <tr className="border-b border-border text-start text-muted">
                  <th scope="col" className="px-4 py-3 text-start font-medium">
                    {t("person")}
                  </th>
                  {columns.map((column) => (
                    <th key={column} scope="col" className="px-4 py-3 text-end font-medium">
                      {t(column)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {summary.people.map((person) => (
                  <tr key={person.user_id} className="border-b border-border last:border-0">
                    <th scope="row" dir="auto" className="px-4 py-3 text-start font-medium">
                      {person.full_name}
                      {person.corrected_months > 0 && (
                        <span className="ms-2">
                          <Pill tone="warning">{t("corrected", { count: person.corrected_months })}</Pill>
                        </span>
                      )}
                    </th>
                    <td className="px-4 py-3 text-end tabular-nums">{person.months}</td>
                    <td className="px-4 py-3 text-end tabular-nums">
                      <bdi>{money(person.gross_minor)}</bdi>
                    </td>
                    <td className="px-4 py-3 text-end tabular-nums">
                      <bdi>{money(person.income_tax_minor)}</bdi>
                    </td>
                    <td className="px-4 py-3 text-end tabular-nums">
                      <bdi>{money(person.national_insurance_minor)}</bdi>
                    </td>
                    <td className="px-4 py-3 text-end tabular-nums">
                      <bdi>{money(person.health_minor)}</bdi>
                    </td>
                    <td className="px-4 py-3 text-end tabular-nums">
                      <bdi>{money(person.pension_employee_minor)}</bdi>
                    </td>
                    <td className="px-4 py-3 text-end font-semibold tabular-nums">
                      <bdi>{money(person.net_minor)}</bdi>
                    </td>
                    <td className="px-4 py-3 text-end tabular-nums">
                      <bdi>{money(person.employer_minor)}</bdi>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Container>
  );
}
