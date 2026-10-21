import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { SupportSection } from "../support-section";
import { TopicHeader } from "../topic-header";
import { WriteToSupport } from "../write-to-support";

/** Settings → Help: support access for the team, and a way to write to us. */
export default async function HelpSettingsPage() {
  const t = await getTranslations("settings");
  const context = await getTenant();
  if (!canManageSettings(context.tenant)) redirect("/dashboard");

  return (
    <div className="form-columns">
      <TopicHeader title={t("nav.items.help")} description={t("nav.hints.help")} />
      {context.tenant.role === "owner" && <SupportSection context={context} />}
      <WriteToSupport />
    </div>
  );
}
