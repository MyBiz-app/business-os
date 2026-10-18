import { getTranslations } from "next-intl/server";

import { RouteModal } from "@/components/ui/route-modal";
import { getTenantFor } from "@/lib/tenant";

import { NewDocumentBody, startsCredit } from "../../../invoices/new/new-document-body";

export default async function NewDocumentModal({ searchParams }: PageProps<"/invoices/new">) {
  const t = await getTranslations("invoices");
  await getTenantFor("sales.manage");
  const params = await searchParams;
  return (
    <RouteModal title={startsCredit(params) ? t("newCredit") : t("new")} size="lg">
      <NewDocumentBody params={params} plain />
    </RouteModal>
  );
}
