import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { canWriteClients } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { createClient } from "../actions";
import { ClientForm } from "../client-form";

export default async function NewClientPage() {
  const t = await getTranslations();
  const { tenant } = await getTenantFor("clients.read");
  if (!canWriteClients(tenant)) redirect("/clients");

  return (
    <main className="enter mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <h1 className="text-3xl font-bold">{t(`terms.${tenant.vertical}.newClient` as "terms.fitness.newClient")}</h1>
      <ClientForm action={createClient} submitLabel={t("clients.create")} />
    </main>
  );
}
