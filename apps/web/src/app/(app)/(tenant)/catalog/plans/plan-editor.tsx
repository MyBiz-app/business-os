import { getTranslations } from "next-intl/server";
import { notFound, redirect } from "next/navigation";

import { canDeleteCatalog, canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { DeleteButton } from "../delete-button";
import { CatalogPage } from "../page-shell";
import { deletePlan, createPlan, updatePlan } from "./actions";
import { PlanForm } from "./plan-form";

const BACK = "/catalog?tab=plans";

/** A new plan. `modal`: a window over the list; otherwise a page (the shared link). */
export async function NewPlan({ modal }: { modal: boolean }) {
  const t = await getTranslations();
  const { tenant } = await getTenantFor("catalog.read");
  if (!canWriteCatalog(tenant)) redirect("/catalog?tab=plans");
  const form = <PlanForm modal={modal} action={createPlan} currency={tenant.currency} submitLabel={t("common.create")} />;
  return modal ? form : <CatalogPage title={t("plans.new")} backHref={BACK}>{form}</CatalogPage>;
}

/** One plan to view or edit (read-only for people who may not change the catalog). */
export async function PlanEditor({ id, modal }: { id: string; modal: boolean }) {
  const t = await getTranslations();
  const { tenant, api, scope } = await getTenantFor("catalog.read");
  const { data: plan } = await api.GET("/plans/{plan_id}", { params: { ...scope, path: { plan_id: id } } });
  if (!plan) notFound();
  const form = (
    <PlanForm
      modal={modal}
      action={updatePlan.bind(null, plan.id)}
      plan={plan}
      currency={plan.price_currency}
      submitLabel={t("common.save")}
      readOnly={!canWriteCatalog(tenant)}
      aside={
        canDeleteCatalog(tenant) ? (
          <DeleteButton action={deletePlan.bind(null, plan.id)} label={t("plans.delete")} confirm={t("plans.deleteConfirm", { name: plan.name })} />
        ) : undefined
      }
    />
  );
  return modal ? form : <CatalogPage title={<bdi dir="auto">{plan.name}</bdi>} backHref={BACK}>{form}</CatalogPage>;
}
