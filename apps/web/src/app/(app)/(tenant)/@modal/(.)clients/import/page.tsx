import { getTranslations } from "next-intl/server";

import { RouteModal } from "@/components/ui/route-modal";
import { getTenantFor } from "@/lib/tenant";

import { ImportForm } from "../../../clients/import/import-form";

export default async function ImportClientsModal() {
  const t = await getTranslations("clientImport");
  await getTenantFor("clients.write");
  return (
    <RouteModal title={t("title")} description={t("intro")}>
      <ImportForm />
    </RouteModal>
  );
}
