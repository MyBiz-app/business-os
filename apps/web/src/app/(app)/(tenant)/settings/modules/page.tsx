import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

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
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/settings" className="text-sm text-primary underline-offset-4 hover:underline">
        {tSettings("title")}
      </Link>
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <p className="text-sm text-muted">{t("subtitle", { count: current.active_clients })}</p>
      </div>
      <section className="rounded-2xl border border-border bg-surface p-6">
        <ModulesForm catalog={catalog} selection={current.modules} activeClients={current.active_clients} />
      </section>
    </main>
  );
}
