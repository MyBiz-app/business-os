import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { TopicHeader } from "../topic-header";

import { ModulesForm } from "./modules-form";

export default async function ModulesPage() {
  const t = await getTranslations("modules");
  const { tenant, api, scope } = await getTenant();
  if (!canManageSettings(tenant)) redirect("/dashboard");
  const [catalog, current] = await Promise.all([
    api.GET("/modules/catalog", { params: { query: { currency: tenant.currency } } }).then(unwrap),
    api.GET("/tenants/current/modules", { params: scope }).then(unwrap),
  ]);

  return (
    <div className="form-columns">
      <TopicHeader title={t("title")} description={t("subtitle", { count: current.active_clients })} />
      <section className="card p-6">
        <ModulesForm catalog={catalog} selection={current.modules} activeClients={current.active_clients} />
      </section>
    </div>
  );
}
