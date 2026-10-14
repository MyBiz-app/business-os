import { getTranslations } from "next-intl/server";
import { DoorOpen, MapPin } from "lucide-react";
import Link from "next/link";

import { unwrap } from "@/lib/api";
import { canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/empty-state";

export default async function LocationsPage() {
  const t = await getTranslations();
  const { tenant, api, scope } = await getTenantFor("catalog.read");
  const locations = unwrap(await api.GET("/locations", { params: scope }));

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader
        title={t("locations.title")}
        description={t("locations.subtitle")}
        actions={
          canWriteCatalog(tenant) && (
            <Link href="/locations/new" className="btn-primary px-4 py-2.5">
              {t("locations.add")}
            </Link>
          )
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
                <span aria-hidden="true" className="inline-flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <MapPin className="size-5" />
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-1">
                  <span dir="auto" className="font-semibold">{location.name}</span>
                  {location.address && <span dir="auto" className="text-sm text-muted">{location.address}</span>}
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
    </Container>
  );
}
