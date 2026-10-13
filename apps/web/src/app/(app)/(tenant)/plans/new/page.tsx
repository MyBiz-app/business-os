import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { createPlan } from "../actions";
import { PlanForm } from "../plan-form";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

export default async function NewPlanPage() {
  const t = await getTranslations();
  const { tenant } = await getTenantFor("catalog.read");
  if (!canWriteCatalog(tenant)) redirect("/plans");

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader title={t("plans.new")} />
      <PlanForm action={createPlan} currency={tenant.currency} submitLabel={t("common.create")} />
    </Container>
  );
}
