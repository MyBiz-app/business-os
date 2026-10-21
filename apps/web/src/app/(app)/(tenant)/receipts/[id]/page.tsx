import { getTranslations } from "next-intl/server";

import { BackLink } from "@/components/back-link";
import { Container } from "@/components/layout/container";
import { DownloadLink } from "@/components/download-link";
import { PageHeader } from "@/components/layout/page-header";
import { PrintButton } from "@/components/print-button";

import { loadReceipt, ReceiptBody } from "./receipt-body";

/** A payment's receipt, laid out as a printable document. */
export default async function ReceiptPage({ params }: PageProps<"/receipts/[id]">) {
  const { id } = await params;
  const t = await getTranslations("receipts");
  const { receipt } = await loadReceipt(id);

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10 print:max-w-none print:p-0">
      <BackLink href="/sales" label={t("back")} />
      <PageHeader
        className="print:hidden"
        title={t("title", { number: receipt.number })}
        description={<span dir="auto">{receipt.client_name}</span>}
        actions={
          <>
            <DownloadLink href={`/receipts/${id}/pdf`} label={t("download")} />
            <PrintButton label={t("print")} />
          </>
        }
      />
      <ReceiptBody id={id} />
    </Container>
  );
}
