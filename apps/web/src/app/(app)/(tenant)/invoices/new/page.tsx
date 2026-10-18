import { getTranslations } from "next-intl/server";
import Link from "next/link";

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
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <Link href="/invoices" className="text-sm text-primary-ink underline-offset-4 hover:underline">{t("back")}</Link>
      <PageHeader title={startsCredit(params) ? t("newCredit") : t("new")} />
      <NewDocumentBody params={params} />
    </Container>
  );
}
