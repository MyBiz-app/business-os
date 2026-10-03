import { getTranslations } from "next-intl/server";
import Link from "next/link";

import { unwrap } from "@/lib/api";
import { canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

export default async function LocationsPage() {
  const t = await getTranslations();
  const { tenant, api, scope } = await getTenantFor("catalog.read");
  const locations = unwrap(await api.GET("/locations", { params: scope }));

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold">{t("locations.title")}</h1>
          <p className="text-sm text-muted">{t("locations.subtitle")}</p>
        </div>
        {canWriteCatalog(tenant) && (
          <Link href="/locations/new" className="rounded-lg bg-primary px-4 py-2.5 font-semibold text-on-primary">
            {t("locations.add")}
          </Link>
        )}
      </div>

      {locations.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border p-10 text-center text-muted">{t("locations.empty")}</p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {locations.map((location) => (
            <li key={location.id}>
              <Link
                href={`/locations/${location.id}`}
                className={`flex flex-col gap-1 rounded-2xl border border-border bg-surface p-4 hover:border-primary ${location.active ? "" : "opacity-60"}`}
              >
                <span className="font-semibold">{location.name}</span>
                {location.address && <span className="text-sm text-muted">{location.address}</span>}
                <span className="text-sm text-muted">
                  {t("locations.roomsCount", { count: location.rooms.length })}
                  {!location.active && ` · ${t("common.inactive")}`}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
