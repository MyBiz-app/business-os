import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { canWriteCatalog } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { createPlan } from "../actions";
import { PlanForm } from "../plan-form";

export default async function NewPlanPage() {
  const t = await getTranslations();
  const { tenant } = await getTenant();
  if (!canWriteCatalog(tenant.role)) redirect("/plans");

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <h1 className="text-3xl font-bold">{t("plans.new")}</h1>
      <PlanForm action={createPlan} currency={tenant.currency} submitLabel={t("common.create")} />
    </main>
  );
}
