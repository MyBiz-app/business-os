import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { canWriteCatalog } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { updateLocation } from "../actions";
import { LocationForm } from "../location-form";
import { Rooms } from "../rooms";

export default async function LocationPage({ params }: PageProps<"/locations/[id]">) {
  const { id } = await params;
  const t = await getTranslations();
  const { tenant, api, scope } = await getTenant();
  const { data: location } = await api.GET("/locations/{location_id}", {
    params: { ...scope, path: { location_id: id } },
  });
  if (!location) notFound();
  const readOnly = !canWriteCatalog(tenant);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/locations" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("common.back")}
      </Link>
      <h1 className="text-3xl font-bold">{location.name}</h1>
      <LocationForm
        action={updateLocation.bind(null, location.id)}
        location={location}
        submitLabel={t("common.save")}
        readOnly={readOnly}
      />
      <section aria-labelledby="rooms-heading" className="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-6">
        <h2 id="rooms-heading" className="text-lg font-semibold">
          {t("locations.rooms")}
        </h2>
        <Rooms locationId={location.id} rooms={location.rooms} readOnly={readOnly} />
      </section>
    </main>
  );
}
