import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { canWriteClients } from "@/lib/permissions";

import { createLead } from "../actions";
import { LeadForm } from "../lead-form";
import { getCrm } from "../crm";

export default async function NewLeadPage() {
  const t = await getTranslations("leads");
  const { tenant, api, scope } = await getCrm();
  if (!canWriteClients(tenant)) redirect("/leads");
  const owners = unwrap(await api.GET("/leads/owners", { params: scope }));

  return (
    <main className="enter mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/leads" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("back")}
      </Link>
      <h1 className="text-3xl font-bold">{t("new")}</h1>
      <section className="card p-6">
        <LeadForm action={createLead} owners={owners} submitLabel={t("create")} />
      </section>
    </main>
  );
}
