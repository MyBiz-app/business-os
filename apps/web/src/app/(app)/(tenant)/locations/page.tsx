import { getTranslations } from "next-intl/server";
import { DoorOpen, MapPin } from "lucide-react";
import Link from "next/link";

import { unwrap } from "@/lib/api";
import { canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";
import { industryTexts } from "@/lib/verticals";
import { canManageSettings } from "@/lib/permissions";

import { deleteLocationGroup, saveLocationGroup, updateNetworkScope } from "./actions";
import { LocationGroups } from "./location-groups";
import { NetworkPolicy } from "./network-policy";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/empty-state";
import { CollapsibleSection } from "@/components/ui/collapsible-section";

export default async function LocationsPage() {
  const t = await getTranslations();
  const { tenant, api, scope } = await getTenantFor("catalog.read");
  const { text } = industryTexts(t);
  const locations = unwrap(await api.GET("/locations", { params: scope }));
  const groups = unwrap(await api.GET("/location-groups", { params: scope }));

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader
        title={t("locations.title")}
        description={t("locations.subtitle")}
        actions={
          <>
            {tenant.permissions.includes("reports.read") && locations.some((l) => l.active && l.latitude !== null) && (
              <Link href="/locations/map" className="btn-secondary px-4 py-2.5">
                {t("branchMap.title")}
              </Link>
            )}
            {canWriteCatalog(tenant) && (
              <Link href="/locations/new" className="btn-primary px-4 py-2.5">
                {t("locations.add")}
              </Link>
            )}
          </>
        }
      />

      {locations.length === 0 ? (
        <EmptyState variant="list">{t("locations.empty")}</EmptyState>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {locations.map((location) => (
            <li key={location.id}>
              <Link
                href={`/locations/${location.id}`}
                className={`flex h-full items-start gap-3 card card-hover p-5 ${location.active ? "" : "opacity-60"}`}
              >
                <span aria-hidden="true" className="inline-flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary-ink">
                  <MapPin className="size-5" />
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-1">
                  <span dir="auto" className="font-semibold">{location.name}</span>
                  {location.address && <span dir="auto" className="text-sm text-muted">{location.address}</span>}
                  {location.kind && <span className="w-fit rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary-ink">{text(location.kind, "name")}</span>}
                  <span className="inline-flex items-center gap-1.5 text-sm text-muted">
                    <DoorOpen aria-hidden="true" className="size-4" />
                    {t("locations.roomsCount", { count: location.rooms.length })}
                    {!location.active && ` · ${t("common.inactive")}`}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {canManageSettings(tenant) && (
        <CollapsibleSection title={t("locations.settingsTitle")} description={t("locations.settingsHint")} storageKey="locations-settings">
          <div className="flex flex-col gap-6">
            <NetworkPolicy action={updateNetworkScope} scope={tenant.network_scope} multiBranch={locations.length > 1} />
            {locations.length > 1 && (
              <LocationGroups
                branches={locations.map(({ id, name }) => ({ id, name }))}
                groups={groups}
                saveGroup={saveLocationGroup}
                removeGroup={deleteLocationGroup}
              />
            )}
          </div>
        </CollapsibleSection>
      )}
    </Container>
  );
}
