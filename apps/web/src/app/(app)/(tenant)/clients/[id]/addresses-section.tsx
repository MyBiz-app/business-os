import { MapPin, Plus } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { googleMapsLink, wazeLink } from "@/lib/maps";
import { canWriteClients } from "@/lib/permissions";
import type { getTenant } from "@/lib/tenant";

import { setAddressActive } from "./addresses-actions";
import { AddressForm } from "./addresses-forms";

type Context = Awaited<ReturnType<typeof getTenant>>;

/** The client's addresses, where on-site jobs happen (#42); shown when the business has an
 * on-site service or the client already has an address. */
export async function AddressesSection({ clientId, context, locked }: { clientId: string; context: Context; locked: boolean }) {
  const { api, scope, tenant } = context;
  const [addresses, services] = await Promise.all([
    api.GET("/clients/{client_id}/addresses", { params: { ...scope, path: { client_id: clientId } } }).then(unwrap),
    api.GET("/services", { params: { ...scope, query: { active: true } } }).then((r) => r.data ?? []),
  ]);
  if (addresses.length === 0 && !services.some((s) => s.on_site)) return null;
  const t = await getTranslations("jobs.address");
  const writable = !locked && canWriteClients(tenant);
  const line = (a: (typeof addresses)[number]) => [a.street, a.details, a.city].filter(Boolean).join(", ");

  return (
    <section aria-labelledby="addresses-heading" className="flex flex-col gap-4 card p-6">
      <h2 id="addresses-heading" className="flex items-center gap-2 text-lg font-semibold">
        <MapPin aria-hidden="true" className="size-5 text-primary" />
        {t("title")}
      </h2>
      {addresses.length === 0 && <p className="text-sm text-muted">{t("none")}</p>}
      <ul className="flex flex-col gap-3">
        {addresses.map((address) => (
          <li key={address.id} className="flex flex-col gap-2 rounded-xl border border-border p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                {address.label && <span className="font-semibold" dir="auto">{address.label}</span>}
                <span dir="auto">{line(address)}</span>
                {!address.active && <Pill tone="muted">{t("inactive")}</Pill>}
              </div>
              <div className="flex flex-wrap gap-2">
                <a href={wazeLink(line(address))} target="_blank" rel="noreferrer" className="btn-secondary px-2.5 py-1 text-xs">Waze</a>
                <a href={googleMapsLink(line(address))} target="_blank" rel="noreferrer" className="btn-secondary px-2.5 py-1 text-xs">Google Maps</a>
                {writable && (
                  <form action={setAddressActive.bind(null, clientId, address.id, !address.active)}>
                    <button type="submit" aria-label={`${address.active ? t("retire") : t("restore")} – ${line(address)}`} className="btn-secondary px-2.5 py-1 text-xs">
                      {address.active ? t("retire") : t("restore")}
                    </button>
                  </form>
                )}
              </div>
            </div>
            {address.notes && <p dir="auto" className="text-sm text-muted">{address.notes}</p>}
            {writable && (
              <details>
                <summary className="cursor-pointer text-sm text-primary">{t("edit")}</summary>
                <div className="pt-3">
                  <AddressForm clientId={clientId} address={address} />
                </div>
              </details>
            )}
          </li>
        ))}
      </ul>
      {writable && (
        <details className="rounded-xl bg-foreground/[0.03] p-3">
          <summary className="flex cursor-pointer items-center gap-1 text-sm font-medium text-primary">
            <Plus aria-hidden="true" className="size-4" /> {t("add")}
          </summary>
          <div className="pt-3">
            <AddressForm clientId={clientId} />
          </div>
        </details>
      )}
    </section>
  );
}
