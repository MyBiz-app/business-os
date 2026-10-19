import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";

import { BackLink } from "@/components/back-link";
import { HoursForm } from "@/components/form/hours-form";
import { OpeningHoursList } from "@/components/opening-hours";
import { apiAssetUrl } from "@/lib/api";
import { weekStartFor } from "@/lib/hours";
import { canManageSettings, canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";
import { branchKindOptions, industryTexts } from "@/lib/verticals";

import { ContactEmails } from "../../settings/contact-emails";
import { saveOpeningHours, updateLocation } from "../actions";
import { BranchBranding } from "../branch-branding";
import { BranchManager } from "../branch-manager";
import { LocationForm } from "../location-form";
import { Rooms } from "../rooms";
import { UserText } from "@/components/bidi";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

export default async function LocationPage({ params }: PageProps<"/locations/[id]">) {
  const { id } = await params;
  const t = await getTranslations();
  const { tenant, api, scope } = await getTenantFor("catalog.read");
  const { data: location } = await api.GET("/locations/{location_id}", {
    params: { ...scope, path: { location_id: id } },
  });
  if (!location) notFound();
  const readOnly = !canWriteCatalog(tenant);
  // Appointing a manager is for those who reach every branch (owner, manager).
  const team = canManageSettings(tenant) ? (await api.GET("/staff", { params: scope })).data : undefined;
  const managers = (team?.members ?? []).map((m) => ({ id: m.user_id, label: m.full_name ?? m.email }));
  const emails = canManageSettings(tenant)
    ? (await api.GET("/contact-emails", { params: { ...scope, query: { location_id: id } } })).data
    : undefined;
  const hours = (await api.GET("/locations/{location_id}/hours", { params: { ...scope, path: { location_id: id } } })).data;

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/locations" label={t("nav.locations")} />
      <PageHeader title={<UserText>{location.name}</UserText>} />
      <section aria-labelledby="details-heading" className="card flex flex-col gap-4 p-6">
        <h2 id="details-heading" className="text-lg font-semibold">
          {t("locations.detailsTitle")}
        </h2>
        <LocationForm
          action={updateLocation.bind(null, location.id)}
          location={location}
          submitLabel={t("common.save")}
          readOnly={readOnly}
          kindOptions={branchKindOptions(tenant.vertical, industryTexts(t).text, t("locations.kindSame"))}
        />
      </section>
      <CollapsibleSection title={t("openingHours.title")} description={t("openingHours.subtitle")} storageKey="branch-hours" defaultOpen>
        {readOnly ? (
          <OpeningHoursList hours={hours?.intervals ?? []} weekStartsOn={weekStartFor(tenant.locale)} />
        ) : (
          <HoursForm
            save={saveOpeningHours.bind(null, location.id)}
            weekStartsOn={weekStartFor(tenant.locale)}
            emptyLabel={t("openingHours.closed")}
            initial={(hours?.intervals ?? []).map((i) => ({ weekday: i.weekday, starts: i.opens.slice(0, 5), ends: i.closes.slice(0, 5) }))}
          />
        )}
      </CollapsibleSection>
      <CollapsibleSection title={t("locations.rooms")} storageKey="branch-rooms">
        <Rooms locationId={location.id} rooms={location.rooms} readOnly={readOnly} />
      </CollapsibleSection>
      {team && (
        <CollapsibleSection title={t("locations.manager.title")} description={t("locations.manager.subtitle")} storageKey="branch-manager">
          <BranchManager location={location} members={managers} />
        </CollapsibleSection>
      )}
      {emails && (
        <CollapsibleSection title={t("settings.contactEmails.branchTitle")} description={t("settings.contactEmails.branchHint")} storageKey="branch-emails">
          <ContactEmails data={emails} locationId={location.id} grouped />
        </CollapsibleSection>
      )}
      {canManageSettings(tenant) && (
        <CollapsibleSection title={t("locations.brandingTitle")} description={t("locations.brandingHint")} storageKey="branch-branding">
          <BranchBranding location={location} logo={apiAssetUrl(location.logo_url)} networkColor={tenant.primary_color} />
        </CollapsibleSection>
      )}
    </Container>
  );
}
