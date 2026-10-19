import { getTranslations } from "next-intl/server";

import { BackLink } from "@/components/back-link";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { getTenantFor } from "@/lib/tenant";

import { NewDocumentBody, startsCredit } from "./new-document-body";

/** A new document. `?client=` picks the client, `?credit=<id>` starts a credit note for an
 * invoice, `?kind=` picks the kind. */
export default async function NewDocumentPage({ searchParams }: PageProps<"/invoices/new">) {
  const t = await getTranslations("invoices");
  await getTenantFor("sales.manage");
  const params = await searchParams;

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/invoices" label={t("back")} />
      <PageHeader title={startsCredit(params) ? t("newCredit") : t("new")} />
      <NewDocumentBody params={params} />
    </Container>
  );
}
