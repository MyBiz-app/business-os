import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { canWriteCatalog } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { updatePlan } from "../actions";
import { PlanForm } from "../plan-form";

export default async function PlanPage({ params }: PageProps<"/plans/[id]">) {
  const { id } = await params;
  const t = await getTranslations();
  const { tenant, api, scope } = await getTenant();
  const { data: plan } = await api.GET("/plans/{plan_id}", { params: { ...scope, path: { plan_id: id } } });
  if (!plan) notFound();

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/plans" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("common.back")}
      </Link>
      <h1 className="text-3xl font-bold">{plan.name}</h1>
      <PlanForm
        action={updatePlan.bind(null, plan.id)}
        plan={plan}
        currency={plan.price_currency}
        submitLabel={t("common.save")}
        readOnly={!canWriteCatalog(tenant)}
      />
    </main>
  );
}
