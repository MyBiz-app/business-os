import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { canWriteClients } from "@/lib/permissions";

import { createLead } from "../actions";
import { LeadForm } from "../lead-form";
import { getCrm } from "../crm";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

export default async function NewLeadPage() {
  const t = await getTranslations("leads");
  const { tenant, api, scope } = await getCrm();
  if (!canWriteClients(tenant)) redirect("/leads");
  const owners = unwrap(await api.GET("/leads/owners", { params: scope }));

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <Link href="/leads" className="text-sm text-primary-ink underline-offset-4 hover:underline">
        {t("back")}
      </Link>
      <PageHeader title={t("new")} />
      <section className="card p-6">
        <LeadForm action={createLead} owners={owners} submitLabel={t("create")} />
      </section>
    </Container>
  );
}
