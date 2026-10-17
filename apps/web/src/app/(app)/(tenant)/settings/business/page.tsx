import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { ContactEmails } from "../contact-emails";
import { LegalReadiness } from "../legal-readiness";
import { DetailsForm, IdentityForm } from "../settings-forms";
import { TopicHeader } from "../topic-header";

/** Settings → Business: details, legal identity, legal readiness and the business's emails. */
export default async function BusinessSettingsPage() {
  const t = await getTranslations("settings");
  const context = await getTenant();
  const { tenant } = context;
  if (!canManageSettings(tenant)) redirect("/dashboard");
  const emails = (await context.api.GET("/contact-emails", { params: context.scope })).data;
  const readiness = (await context.api.GET("/tenants/current/readiness", { params: context.scope })).data;

  return (
    <div className="flex flex-col gap-6">
      <TopicHeader title={t("nav.items.business")} description={t("nav.hints.business")} />
      <CollapsibleSection title={t("details")} description={t("detailsHint")} defaultOpen storageKey="settings-details">
        <DetailsForm tenant={tenant} timeZones={Intl.supportedValuesOf("timeZone")} />
      </CollapsibleSection>
      <CollapsibleSection title={t("identity.title")} description={t("identity.subtitle")} storageKey="settings-identity">
        <IdentityForm type={tenant.legal_entity_type ?? null} number={tenant.business_number ?? null} />
      </CollapsibleSection>
      {readiness && (
        <div id="readiness-heading" className="scroll-mt-24">
          <CollapsibleSection title={t("readiness.title")} description={t("readiness.subtitle")} storageKey="settings-readiness">
            <LegalReadiness tenant={tenant} readiness={readiness} />
          </CollapsibleSection>
        </div>
      )}
      {emails && <ContactEmails data={emails} locationId={null} />}
    </div>
  );
}
