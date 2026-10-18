import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { TopicHeader } from "../topic-header";
import { FreezeRulesForm } from "./freeze-rules-form";

/** Settings → Memberships and freezes: whether clients may ask to freeze from the app, and the rules. */
export default async function MembershipSettingsPage() {
  const t = await getTranslations("settings");
  const { tenant, api, scope } = await getTenant();
  if (!canManageSettings(tenant)) redirect("/dashboard");
  const rules = unwrap(await api.GET("/freeze-rules", { params: scope }));

  return (
    <div className="flex flex-col gap-6">
      <TopicHeader title={t("freezeRules.title")} description={t("nav.hints.memberships")} />
      <FreezeRulesForm key={JSON.stringify(rules)} rules={rules} currency={tenant.currency} />
    </div>
  );
}
