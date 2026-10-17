import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { getTenant } from "@/lib/tenant";

import { CloseSection } from "../close-section";
import { ExportSection } from "../export-section";
import { TopicHeader } from "../topic-header";

/** Settings → Data and privacy: export the business, close it. Owners only. */
export default async function DataSettingsPage() {
  const t = await getTranslations("settings");
  const context = await getTenant();
  if (context.tenant.role !== "owner") redirect("/settings/business");

  return (
    <div className="flex flex-col gap-6">
      <TopicHeader title={t("nav.items.data")} description={t("nav.hints.data")} />
      <ExportSection context={context} />
      <CloseSection name={context.tenant.name} />
    </div>
  );
}
