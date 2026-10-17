import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { redirect } from "next/navigation";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { unwrap } from "@/lib/api";
import { getBranches, getTenant } from "@/lib/tenant";

import { BonusForm } from "./bonus-form";
import { BonusList } from "./bonus-list";

/** One-off amounts for a month: bonuses, holiday gifts, expense refunds and deductions. A payroll
 * manager adds them; a branch manager proposes and the owner decides. */
export default async function BonusesPage({ searchParams }: PageProps<"/team/bonuses">) {
  const t = await getTranslations("payBonuses");
  const common = await getTranslations("common");
  const { tenant, api, scope } = await getTenant();
  const permissions = tenant.permissions;
  if (!permissions.includes("payroll.manage") && !permissions.includes("payroll.propose")) redirect("/dashboard");

  const month = (await searchParams).month;
  const now = new Date();
  const current = typeof month === "string" && /^\d{4}-\d{2}$/.test(month) ? month : `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const [team, groups, adjustments, branches] = await Promise.all([
    api.GET("/staff", { params: scope }).then(unwrap),
    api.GET("/location-groups", { params: scope }).then(unwrap),
    api
      .GET("/payroll/bonuses", { params: { ...scope, query: { period: `${current}-01` } } })
      .then(unwrap),
    getBranches(),
  ]);
  const locale = await getLocale();

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-8 py-8 sm:py-10">
      <Link href="/team" className="text-sm text-primary-ink underline-offset-4 hover:underline">
        {common("back")}
      </Link>
      <PageHeader title={t("title")} description={t("description")} />
      <BonusForm
        currency={tenant.currency}
        locale={locale}
        month={current}
        canManage={permissions.includes("payroll.manage")}
        members={team.members.map((m) => ({ id: m.user_id, name: m.full_name ?? m.email }))}
        branches={branches.map((b) => ({ id: b.id, name: b.name }))}
        groups={groups.map((g) => ({ id: g.id, name: g.name }))}
      />
      <BonusList
        currency={tenant.currency}
        locale={locale}
        month={current}
        rows={adjustments}
        canApprove={permissions.includes("payroll.approve")}
        canManage={permissions.includes("payroll.manage")}
      />
    </Container>
  );
}
