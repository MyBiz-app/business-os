import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { canWriteClients } from "@/lib/permissions";
import { getBranches, getTenantFor } from "@/lib/tenant";

import { createClient } from "../actions";
import { ClientForm } from "../client-form";

/** The add-client form: the page and the window over the list show the same thing. */
export async function NewClientBody() {
  const t = await getTranslations("clients");
  const { tenant, branch } = await getTenantFor("clients.read");
  const branches = await getBranches();
  if (!canWriteClients(tenant)) redirect("/clients");
  return <ClientForm action={createClient} submitLabel={t("create")} branches={branches} defaultBranch={branch} />;
}
