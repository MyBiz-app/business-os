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

import { saveOpeningHours, updateLocation } from "../actions";
import { BranchBranding } from "../branch-branding";
import { BranchManager } from "../branch-manager";
import { LocationForm } from "../location-form";
import { Rooms } from "../rooms";
import { UserText } from "@/components/bidi";
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
  const hours = (await api.GET("/locations/{location_id}/hours", { params: { ...scope, path: { location_id: id } } })).data;

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/locations" label={t("nav.locations")} />
      <PageHeader title={<UserText>{location.name}</UserText>} />
      <LocationForm
        action={updateLocation.bind(null, location.id)}
        location={location}
        submitLabel={t("common.save")}
        readOnly={readOnly}
        kindOptions={branchKindOptions(tenant.vertical, industryTexts(t).text, t("locations.kindSame"))}
      />
      {team && <BranchManager location={location} members={managers} />}
      {canManageSettings(tenant) && <BranchBranding location={location} logo={apiAssetUrl(location.logo_url)} networkColor={tenant.primary_color} />}
      <section aria-labelledby="opening-heading" className="flex flex-col gap-4 card p-6">
        <div className="flex flex-col gap-1">
          <h2 id="opening-heading" className="text-lg font-semibold">
            {t("openingHours.title")}
          </h2>
          <p className="text-sm text-muted">{t("openingHours.subtitle")}</p>
        </div>
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
      </section>
      <section aria-labelledby="rooms-heading" className="flex flex-col gap-4 card p-6">
        <h2 id="rooms-heading" className="text-lg font-semibold">
          {t("locations.rooms")}
        </h2>
        <Rooms locationId={location.id} rooms={location.rooms} readOnly={readOnly} />
      </section>
    </Container>
  );
}
