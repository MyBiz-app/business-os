import { getTranslations } from "next-intl/server";

import { getTenantFor } from "@/lib/tenant";

import { ImportForm } from "./import-form";
import { BackLink } from "@/components/back-link";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

export default async function ImportClientsPage() {
  const t = await getTranslations("clientImport");
  const tClients = await getTranslations("clients");
  await getTenantFor("clients.write");

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/clients" label={tClients("back")} />
      <PageHeader title={t("title")} description={t("intro")} />
      <ImportForm />
    </Container>
  );
}
