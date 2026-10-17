import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { canWriteClients } from "@/lib/permissions";

import { createLead } from "../actions";
import { getCrm } from "../crm";
import { LeadForm } from "../lead-form";

/** The new-lead form: the page and the window over the leads list show the same thing. */
export async function NewLeadBody() {
  const t = await getTranslations("leads");
  const { tenant, api, scope } = await getCrm();
  if (!canWriteClients(tenant)) redirect("/leads");
  const owners = unwrap(await api.GET("/leads/owners", { params: scope }));
  return <LeadForm action={createLead} owners={owners} submitLabel={t("create")} />;
}
