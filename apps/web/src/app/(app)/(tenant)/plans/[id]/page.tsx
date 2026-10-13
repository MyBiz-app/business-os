import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ConfirmDelete } from "@/components/form/confirm-delete";
import { canDeleteCatalog, canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { deletePlan, updatePlan } from "../actions";
import { PlanForm } from "../plan-form";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

export default async function PlanPage({ params }: PageProps<"/plans/[id]">) {
  const { id } = await params;
  const t = await getTranslations();
  const { tenant, api, scope } = await getTenantFor("catalog.read");
  const { data: plan } = await api.GET("/plans/{plan_id}", { params: { ...scope, path: { plan_id: id } } });
  if (!plan) notFound();

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <Link href="/plans" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("common.back")}
      </Link>
      <PageHeader title={<bdi dir="auto">{plan.name}</bdi>} />
      <PlanForm
        action={updatePlan.bind(null, plan.id)}
        plan={plan}
        currency={plan.price_currency}
        submitLabel={t("common.save")}
        readOnly={!canWriteCatalog(tenant)}
      />
      {canDeleteCatalog(tenant) && (
        <ConfirmDelete action={deletePlan.bind(null, plan.id)} label={t("plans.delete")} confirm={t("plans.deleteConfirm", { name: plan.name })} />
      )}
    </Container>
  );
}
