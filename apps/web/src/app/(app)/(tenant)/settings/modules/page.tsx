import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

import { ModulesForm } from "./modules-form";

export default async function ModulesPage() {
  const t = await getTranslations("modules");
  const tSettings = await getTranslations("settings");
  const { tenant, api, scope } = await getTenant();
  if (!canManageSettings(tenant)) redirect("/dashboard");
  const [catalog, current] = await Promise.all([
    api.GET("/modules/catalog", { params: { query: { currency: tenant.currency } } }).then(unwrap),
    api.GET("/tenants/current/modules", { params: scope }).then(unwrap),
  ]);

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <Link href="/settings" className="text-sm text-primary underline-offset-4 hover:underline">
        {tSettings("title")}
      </Link>
      <PageHeader title={t("title")} description={t("subtitle", { count: current.active_clients })} />
      <section className="card p-6">
        <ModulesForm catalog={catalog} selection={current.modules} activeClients={current.active_clients} />
      </section>
    </Container>
  );
}
