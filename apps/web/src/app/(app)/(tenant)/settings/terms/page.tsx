import { TERM_KEYS } from "@business-os/verticals";
import { getLocale, getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";
import { businessTerms } from "@/lib/verticals";

import { TopicHeader } from "../topic-header";
import { TermsForm } from "./terms-form";

/** Settings → Our words: the owner renames what the screens call things ("clients" to "club
 * members"), in the language of the page. */
export default async function TermsSettingsPage() {
  const t = await getTranslations("settings");
  const tAll = await getTranslations();
  const locale = await getLocale();
  const { tenant } = await getTenant();
  if (!canManageSettings(tenant)) redirect("/dashboard");
  const industry = businessTerms(tAll, { vertical: tenant.vertical }, locale);
  const defaults = Object.fromEntries(TERM_KEYS.map((key) => [key, industry(key)]));

  return (
    <div className="form-columns">
      <TopicHeader title={t("nav.items.terms")} description={t("nav.hints.terms")} />
      <CollapsibleSection title={t("terms.title")} description={t("terms.subtitle")} defaultOpen storageKey="settings-terms-v1">
        <TermsForm defaults={defaults} current={tenant.terms_override?.[locale] ?? {}} />
      </CollapsibleSection>
    </div>
  );
}
