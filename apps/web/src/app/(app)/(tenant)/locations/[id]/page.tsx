import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";

import { BackLink } from "@/components/back-link";
import { HoursForm } from "@/components/form/hours-form";
import { OpeningHoursList } from "@/components/opening-hours";
import { weekStartFor } from "@/lib/hours";
import { canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { saveOpeningHours, updateLocation } from "../actions";
import { LocationForm } from "../location-form";
import { Rooms } from "../rooms";

export default async function LocationPage({ params }: PageProps<"/locations/[id]">) {
  const { id } = await params;
  const t = await getTranslations();
  const { tenant, api, scope } = await getTenantFor("catalog.read");
  const { data: location } = await api.GET("/locations/{location_id}", {
    params: { ...scope, path: { location_id: id } },
  });
  if (!location) notFound();
  const readOnly = !canWriteCatalog(tenant);
  const hours = (await api.GET("/locations/{location_id}/hours", { params: { ...scope, path: { location_id: id } } })).data;

  return (
    <main className="enter mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <BackLink href="/locations" label={t("nav.locations")} />
      <h1 className="text-3xl font-bold">{location.name}</h1>
      <LocationForm
        action={updateLocation.bind(null, location.id)}
        location={location}
        submitLabel={t("common.save")}
        readOnly={readOnly}
      />
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
    </main>
  );
}
