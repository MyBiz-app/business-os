import { getTranslations } from "next-intl/server";
import { notFound, redirect } from "next/navigation";

import { canDeleteCatalog, canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { RouteModal } from "@/components/ui/route-modal";
import { DeleteButton } from "../delete-button";
import { CatalogPage } from "../page-shell";
import { createService, deleteService, updateService } from "./actions";
import { ServiceForm } from "./service-form";
import { ServiceRooms } from "./service-rooms";

const BACK = "/catalog?tab=services";

/** A new service. `modal`: a window over the list; otherwise a page (the shared link). */
export async function NewService({ modal }: { modal: boolean }) {
  const t = await getTranslations();
  const { tenant } = await getTenantFor("catalog.read");
  if (!canWriteCatalog(tenant)) redirect("/catalog?tab=services");
  const form = <ServiceForm modal={modal} action={createService} currency={tenant.currency} submitLabel={t("common.create")} />;
  return modal ? <RouteModal title={t("services.new")}>{form}</RouteModal> : <CatalogPage title={t("services.new")} backHref={BACK}>{form}</CatalogPage>;
}

/** One service to view or edit (read-only for people who may not change the catalog). */
export async function ServiceEditor({ id, modal }: { id: string; modal: boolean }) {
  const t = await getTranslations();
  const { tenant, api, scope } = await getTenantFor("catalog.read");
  const { data: service } = await api.GET("/services/{service_id}", { params: { ...scope, path: { service_id: id } } });
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

  const form = (
    <ServiceForm
      modal={modal}
      action={updateService.bind(null, service.id)}
      service={service}
      currency={service.price_currency}
      submitLabel={t("common.save")}
      readOnly={readOnly}
      aside={
        <>
          {service.booking_mode === "resource" && <ServiceRooms rooms={bookable} selected={selected} readOnly={readOnly} />}
          {canDeleteCatalog(tenant) && (
            <DeleteButton action={deleteService.bind(null, service.id)} label={t("services.delete")} confirm={t("services.deleteConfirm", { name: service.name })} />
          )}
        </>
      }
    />
  );
  return modal ? <RouteModal title={service.name}>{form}</RouteModal> : <CatalogPage title={<bdi dir="auto">{service.name}</bdi>} backHref={BACK}>{form}</CatalogPage>;
}
