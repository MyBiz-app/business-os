import { getTranslations } from "next-intl/server";

import { RouteModal } from "@/components/ui/route-modal";

import { NewLeadBody } from "../../../leads/new/new-lead-body";

export default async function NewLeadModal() {
  const t = await getTranslations("leads");
  return (
    <RouteModal title={t("new")} size="md">
      <NewLeadBody />
    </RouteModal>
  );
}
