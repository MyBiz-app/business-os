import { getLocale, getTranslations } from "next-intl/server";
import { businessTerms } from "@/lib/verticals";

import { BackLink } from "@/components/back-link";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { getTenantFor } from "@/lib/tenant";

import { NewClientBody } from "./new-client-body";

export default async function NewClientPage() {
  const t = await getTranslations();
  const locale = await getLocale();
  const { tenant } = await getTenantFor("clients.read");
  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/clients" label={t("clients.back")} />
      <PageHeader title={businessTerms(t, tenant, locale)("newClient")} />
      <NewClientBody />
    </Container>
  );
}
