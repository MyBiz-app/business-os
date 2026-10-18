import { getTranslations } from "next-intl/server";

import { RouteModal } from "@/components/ui/route-modal";

import { WizardBody } from "../../../website/brief/wizard-body";

export default async function WebsiteBriefModal() {
  const t = await getTranslations("website");
  return (
    <RouteModal title={t("wizardTitle")} description={t("wizardHint")} size="lg">
      <WizardBody />
    </RouteModal>
  );
}
