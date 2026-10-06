import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { saveServiceRooms, updateService } from "../actions";
import { ServiceForm } from "../service-form";
import { ServiceRooms } from "../service-rooms";

export default async function ServicePage({ params }: PageProps<"/services/[id]">) {
  const { id } = await params;
  const t = await getTranslations();
  const { tenant, api, scope } = await getTenantFor("catalog.read");
  const { data: service } = await api.GET("/services/{service_id}", {
    params: { ...scope, path: { service_id: id } },
  });
  if (!service) notFound();
  const readOnly = !canWriteCatalog(tenant);
  // A resource service is reserved in the bookable rooms chosen for it.
  const [locations, resources] =
    service.booking_mode === "resource"
      ? await Promise.all([
          api.GET("/locations", { params: scope }).then((r) => r.data ?? []),
          api.GET("/resources", { params: scope }).then((r) => r.data ?? []),
        ])
      : [[], []];
  const bookable = locations
    .filter((branch) => branch.active)
    .flatMap((branch) => branch.rooms.filter((room) => room.bookable && room.active).map((room) => ({ id: room.id, name: room.name, branch: branch.name })));
  const selected = resources.find((r) => r.id === service.id)?.rooms.map((room) => room.id) ?? [];

  return (
    <main className="enter mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/services" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("common.back")}
      </Link>
      <h1 className="text-3xl font-bold">{service.name}</h1>
      <ServiceForm
        action={updateService.bind(null, service.id)}
        service={service}
        currency={service.price_currency}
        submitLabel={t("common.save")}
        readOnly={readOnly}
      />
      {service.booking_mode === "resource" && (
        <section aria-labelledby="rooms-heading" className="card flex flex-col gap-4 p-6">
          <div className="flex flex-col gap-1">
            <h2 id="rooms-heading" className="text-lg font-semibold">{t("resources.rooms")}</h2>
            <p className="text-sm text-muted">{t("resources.roomsHint")}</p>
          </div>
          <ServiceRooms action={saveServiceRooms.bind(null, service.id)} rooms={bookable} selected={selected} readOnly={readOnly} />
        </section>
      )}
    </main>
  );
}
