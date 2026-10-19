import { getTranslations } from "next-intl/server";

import { Ltr } from "@/components/bidi";
import { BackLink } from "@/components/back-link";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

import { InvoiceActions, InvoiceBody, loadInvoice } from "./invoice-body";

/** One issued document: what it says, and its PDF (the stored original, or a marked copy). */
export default async function InvoicePage({ params }: PageProps<"/invoices/[id]">) {
  const { id } = await params;
  const t = await getTranslations("invoices");
  const { doc } = await loadInvoice(id);

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/invoices" label={t("back")} />
      <PageHeader
        title={
          <span>
            {t(`kinds.${doc.kind}`)} <Ltr className="tabular-nums">#{doc.number}</Ltr>
          </span>
        }
        actions={<InvoiceActions id={id} />}
      />
      <InvoiceBody id={id} />
    </Container>
  );
}
