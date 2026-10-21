import { DataTable } from "@/components/ui/data-table";
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
import { EmptyState } from "@/components/empty-state";

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
        <EmptyState variant="chart">{t("empty")}</EmptyState>
      ) : (
        <>
          {summary.draft && <p className="text-sm text-muted">{t("draft")}</p>}
          <DataTable
            label={t("person")}
            className="[&_table]:min-w-[48rem]"
            rows={summary.people}
            rowKey={(person) => person.user_id}
            columns={[
              {
                key: "person",
                header: t("person"),
                rowHeader: true,
                cell: (person) => (
                  <span dir="auto">
                    {person.full_name}
                    {person.corrected_months > 0 && (
                      <span className="ms-2">
                        <Pill tone="warning">{t("corrected", { count: person.corrected_months })}</Pill>
                      </span>
                    )}
                  </span>
                ),
              },
              { key: "months", header: t("months"), align: "end", className: "tabular-nums", cell: (person) => person.months },
              { key: "gross", header: t("gross"), align: "end", className: "tabular-nums", cell: (person) => <bdi>{money(person.gross_minor)}</bdi> },
              { key: "tax", header: t("tax"), align: "end", className: "tabular-nums", cell: (person) => <bdi>{money(person.income_tax_minor)}</bdi> },
              { key: "ni", header: t("ni"), align: "end", className: "tabular-nums", cell: (person) => <bdi>{money(person.national_insurance_minor)}</bdi> },
              { key: "health", header: t("health"), align: "end", className: "tabular-nums", cell: (person) => <bdi>{money(person.health_minor)}</bdi> },
              { key: "pension", header: t("pension"), align: "end", className: "tabular-nums", cell: (person) => <bdi>{money(person.pension_employee_minor)}</bdi> },
              { key: "net", header: t("net"), align: "end", className: "font-semibold tabular-nums", cell: (person) => <bdi>{money(person.net_minor)}</bdi> },
              { key: "employer", header: t("employer"), align: "end", className: "tabular-nums", cell: (person) => <bdi>{money(person.employer_minor)}</bdi> },
            ]}
          />
        </>
      )}
    </Container>
  );
}
