import { getTranslations } from "next-intl/server";

import { RouteModal } from "@/components/ui/route-modal";

import { InvoiceActions, InvoiceBody, loadInvoice } from "../../../invoices/[id]/invoice-body";

export default async function InvoiceModal({ params }: PageProps<"/invoices/[id]">) {
  const { id } = await params;
  const t = await getTranslations("invoices");
  const { doc } = await loadInvoice(id);
  return (
    <RouteModal title={`${t(`kinds.${doc.kind}`)} #${doc.number}`} size="lg">
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap gap-2">
          <InvoiceActions id={id} />
        </div>
        <InvoiceBody id={id} />
      </div>
    </RouteModal>
  );
}
