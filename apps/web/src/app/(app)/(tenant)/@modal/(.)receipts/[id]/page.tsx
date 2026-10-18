import { getTranslations } from "next-intl/server";

import { DownloadLink } from "@/components/download-link";
import { PrintButton } from "@/components/print-button";
import { RouteModal } from "@/components/ui/route-modal";

import { loadReceipt, ReceiptBody } from "../../../receipts/[id]/receipt-body";

export default async function ReceiptModal({ params }: PageProps<"/receipts/[id]">) {
  const { id } = await params;
  const t = await getTranslations("receipts");
  const { receipt } = await loadReceipt(id);
  return (
    <RouteModal title={t("title", { number: receipt.number })} size="md" transitionName={`receipt-${id}`}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2 print:hidden">
          <DownloadLink href={`/receipts/${id}/pdf`} label={t("download")} />
          <PrintButton label={t("print")} />
        </div>
        <ReceiptBody id={id} />
      </div>
    </RouteModal>
  );
}
