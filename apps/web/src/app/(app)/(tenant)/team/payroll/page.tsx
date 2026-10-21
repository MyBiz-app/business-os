import { addMonths, monthStart, todayIn } from "@business-os/i18n/dates";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { TeamTabs } from "../team-tabs";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { unwrap } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

import { RunBoard, StartRun } from "./run-board";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("payRun");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** The month's payroll run up to gross pay: hours, additions, review and the owner's approval. */
export default async function PayrollRunPage({ searchParams }: PageProps<"/team/payroll">) {
  const t = await getTranslations("payRun");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("payroll.read");
  const query = await searchParams;
  const requested = typeof query.month === "string" && /^\d{4}-\d{2}$/.test(query.month) ? `${query.month}-01` : null;
  const first = requested ?? monthStart(todayIn(tenant.time_zone));
  const month = first.slice(0, 7);
  const response = await api.GET("/payroll/runs/{period}", { params: { ...scope, path: { period: month } } });
  if (!response.data && response.response.status !== 404) unwrap(response);
  const run = response.data ?? null;
  const label = new Intl.DateTimeFormat(locale, { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${first}T00:00:00Z`));
  const step = (months: number) => `/team/payroll?month=${addMonths(first, months).slice(0, 7)}`;
  const permissions = tenant.permissions;

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <TeamTabs active="payroll" tenant={tenant} />
      <PageHeader title={t("title")} description={t("subtitle")} />
      <nav aria-label={t("monthNav")} className="flex items-center gap-3">
        <Link scroll={false} href={step(-1)} className="btn-secondary px-3 py-2 text-sm">
          {t("previous")}
        </Link>
        <h2 className="text-lg font-semibold">{label}</h2>
        <Link scroll={false} href={step(1)} className="btn-secondary px-3 py-2 text-sm">
          {t("next")}
        </Link>
        {permissions.includes("payroll.approve") && (
          <Link href={`/team/payroll/annual?year=${first.slice(0, 4)}`} className="btn-ghost ms-auto px-3 py-2 text-sm">
            {t("annual.link")}
          </Link>
        )}
      </nav>
      {run ? (
        <RunBoard run={run} month={month} locale={locale} canManage={permissions.includes("payroll.manage")} canApprove={permissions.includes("payroll.approve")} />
      ) : (
        <StartRun month={month} label={label} canManage={permissions.includes("payroll.manage")} />
      )}
    </Container>
  );
}
