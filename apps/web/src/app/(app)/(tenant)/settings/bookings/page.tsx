import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { unwrap } from "@/lib/api";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { TopicHeader } from "../topic-header";
import { ServiceWaitlistRow, WaitlistForm } from "./waitlist-form";

/** Settings → Bookings and waitlists: whether the business keeps waitlists and what happens when a
 * spot opens, for classes, appointments and courts, with a different mode for one service if needed. */
export default async function BookingSettingsPage() {
  const t = await getTranslations("settings");
  const context = await getTenant();
  const { tenant, api, scope } = context;
  if (!canManageSettings(tenant)) redirect("/dashboard");
  const services = unwrap(await api.GET("/services", { params: { ...scope, query: { active: true } } }));

  return (
    <div className="flex flex-col gap-6">
      <TopicHeader title={t("nav.items.bookings")} description={t("nav.hints.bookings")} />
      <CollapsibleSection title={t("waitlist.title")} description={t("waitlist.subtitle")} defaultOpen storageKey="settings-waitlist">
        <WaitlistForm tenant={tenant} />
      </CollapsibleSection>
      {services.length > 0 && (
        <CollapsibleSection title={t("waitlist.perService")} description={t("waitlist.perServiceHint")} storageKey="settings-waitlist-services">
          <ul className="flex flex-col divide-y divide-border">
            {services.map((service) => (
              <ServiceWaitlistRow key={`${service.id}-${service.waitlist_mode}`} id={service.id} name={service.name} mode={service.waitlist_mode ?? ""} />
            ))}
          </ul>
        </CollapsibleSection>
      )}
    </div>
  );
}
