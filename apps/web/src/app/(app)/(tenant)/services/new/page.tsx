import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { createService } from "../actions";
import { ServiceForm } from "../service-form";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

export default async function NewServicePage() {
  const t = await getTranslations();
  const { tenant } = await getTenantFor("catalog.read");
  if (!canWriteCatalog(tenant)) redirect("/services");

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader title={t("services.new")} />
      <ServiceForm action={createService} currency={tenant.currency} submitLabel={t("common.create")} />
    </Container>
  );
}
