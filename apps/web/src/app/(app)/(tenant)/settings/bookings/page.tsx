import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { unwrap } from "@/lib/api";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { TopicHeader } from "../topic-header";
import { CancellationForm, OverrideRow } from "./cancellation-form";
import { ServiceWaitlistRow, WaitlistForm } from "./waitlist-form";

/** Settings → Bookings and waitlists: whether the business keeps waitlists and what happens when a
 * spot opens, for classes, appointments and courts, with a different mode for one service if needed. */
export default async function BookingSettingsPage() {
  const t = await getTranslations("settings");
  const context = await getTenant();
  const { tenant, api, scope } = context;
  if (!canManageSettings(tenant)) redirect("/dashboard");
  const services = unwrap(await api.GET("/services", { params: { ...scope, query: { active: true } } }));
  const cancellation = unwrap(await api.GET("/cancellation-policy", { params: scope }));

  return (
    <div className="form-columns">
      <TopicHeader title={t("nav.items.bookings")} description={t("nav.hints.bookings")} />
      <CollapsibleSection title={t("cancellation.title")} description={t("cancellation.subtitle")} defaultOpen storageKey="settings-cancellation-v2">
        <div className="flex flex-col gap-5">
          <CancellationForm key={JSON.stringify(cancellation.business)} overview={cancellation} />
          {cancellation.services.length > 0 && (
            <CollapsibleSection variant="inline" className="border-t border-border pt-4" title={t("cancellation.perService")}>
              <p className="mb-2 text-sm text-muted">{t("cancellation.perServiceHint")}</p>
              <ul className="flex flex-col divide-y divide-border">
                {cancellation.services.map((service) => (
                  <OverrideRow key={`${service.service_id}-${JSON.stringify(service.policy)}`} kind="service" row={{ id: service.service_id, name: service.name, policy: service.policy }} fallback={cancellation.business} />
                ))}
              </ul>
            </CollapsibleSection>
          )}
          {cancellation.plans.length > 0 && (
            <CollapsibleSection variant="inline" className="border-t border-border pt-4" title={t("cancellation.perPlan")}>
              <p className="mb-2 text-sm text-muted">{t("cancellation.perPlanHint")}</p>
              <ul className="flex flex-col divide-y divide-border">
                {cancellation.plans.map((plan) => (
                  <OverrideRow key={`${plan.plan_id}-${JSON.stringify(plan.policy)}`} kind="plan" row={{ id: plan.plan_id, name: plan.name, policy: plan.policy }} fallback={cancellation.business} />
                ))}
              </ul>
            </CollapsibleSection>
          )}
        </div>
      </CollapsibleSection>
      <CollapsibleSection title={t("waitlist.title")} description={t("waitlist.subtitle")} storageKey="settings-waitlist-v2">
        <div className="flex flex-col gap-5">
          <WaitlistForm tenant={tenant} />
          {services.length > 0 && (
            <CollapsibleSection variant="inline" className="border-t border-border pt-4" title={t("waitlist.perService")}>
              <p className="mb-2 text-sm text-muted">{t("waitlist.perServiceHint")}</p>
              <ul className="flex flex-col divide-y divide-border">
                {services.map((service) => (
                  <ServiceWaitlistRow key={`${service.id}-${service.waitlist_mode}`} id={service.id} name={service.name} mode={service.waitlist_mode ?? ""} />
                ))}
              </ul>
            </CollapsibleSection>
          )}
        </div>
      </CollapsibleSection>
    </div>
  );
}
