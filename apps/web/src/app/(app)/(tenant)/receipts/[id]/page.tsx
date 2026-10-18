import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { Container } from "@/components/layout/container";
import { DownloadLink } from "@/components/download-link";
import { PrintButton } from "@/components/print-button";

import { loadReceipt, ReceiptBody } from "./receipt-body";

/** A payment's receipt, laid out as a printable document. */
export default async function ReceiptPage({ params }: PageProps<"/receipts/[id]">) {
  const { id } = await params;
  const t = await getTranslations("receipts");
  const { receipt } = await loadReceipt(id);

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10 print:max-w-none print:p-0">
      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <Link href={`/clients/${receipt.client_id}`} className="text-sm text-primary-ink underline-offset-4 hover:underline">
          {t("back")}
        </Link>
        <div className="flex flex-wrap items-center gap-2">
          <DownloadLink href={`/receipts/${id}/pdf`} label={t("download")} />
          <PrintButton label={t("print")} />
        </div>
      </div>
      <ReceiptBody id={id} />
    </Container>
  );
}
