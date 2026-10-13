import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";
import { termsOf } from "@business-os/verticals";

import { canWriteClients } from "@/lib/permissions";
import { getBranches, getTenantFor } from "@/lib/tenant";

import { createClient } from "../actions";
import { ClientForm } from "../client-form";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

export default async function NewClientPage() {
  const t = await getTranslations();
  const { tenant, branch } = await getTenantFor("clients.read");
  const branches = await getBranches();
  if (!canWriteClients(tenant)) redirect("/clients");

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader title={t(`terms.${termsOf(tenant.vertical)}.newClient` as "terms.fitness.newClient")} />
      <ClientForm action={createClient} submitLabel={t("clients.create")} branches={branches} defaultBranch={branch} />
    </Container>
  );
}
