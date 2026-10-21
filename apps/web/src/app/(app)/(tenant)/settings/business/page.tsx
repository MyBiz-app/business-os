import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { canManageSettings } from "@/lib/permissions";
import { isSolo } from "@/lib/solo";
import { getTenant } from "@/lib/tenant";

import { ContactEmails } from "../contact-emails";
import { LegalReadiness } from "../legal-readiness";
import { DetailsForm, IdentityForm } from "../settings-forms";
import { SettingsGroup } from "../settings-group";
import { SoloCard } from "../solo-card";
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
    <div className="flex flex-col gap-8">
      <TopicHeader title={t("nav.items.business")} description={t("nav.hints.business")} />
      {isSolo(tenant) && <SoloCard />}
      <SettingsGroup id="identity" title={t("identity.title")} description={t("identity.subtitle")}>
        <IdentityForm type={tenant.legal_entity_type ?? null} number={tenant.business_number ?? null} />
      </SettingsGroup>
      {readiness && (
        <SettingsGroup id="readiness-heading" title={t("readiness.title")} description={t("readiness.subtitle")}>
          <LegalReadiness tenant={tenant} readiness={readiness} />
        </SettingsGroup>
      )}
      <SettingsGroup id="details" title={t("details")} description={t("detailsHint")}>
        <DetailsForm tenant={tenant} timeZones={Intl.supportedValuesOf("timeZone")} />
      </SettingsGroup>
      {emails && (
        <SettingsGroup id="emails" title={t("contactEmails.title")} description={t("contactEmails.hint")}>
          <ContactEmails data={emails} locationId={null} grouped />
        </SettingsGroup>
      )}
    </div>
  );
}
