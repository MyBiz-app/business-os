import { MapPin, Plus } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Badge } from "@/components/ui/badge";
import { unwrap } from "@/lib/api";
import { googleMapsLink, wazeLink } from "@/lib/maps";
import { canWriteClients } from "@/lib/permissions";
import type { getTenant } from "@/lib/tenant";

import { setAddressActive } from "./addresses-actions";
import { AddressForm } from "./addresses-forms";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { Card } from "@/components/ui/card";
import { Button, ButtonLink } from "@/components/ui/button";

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
    <Card as="section" aria-labelledby="addresses-heading" className="flex flex-col gap-4">
      <h2 id="addresses-heading" className="flex items-center gap-2 text-lg font-semibold">
        <MapPin aria-hidden="true" className="size-5 text-primary-ink" />
        {t("title")}
      </h2>
      {addresses.length === 0 && <p className="text-sm text-muted">{t("none")}</p>}
      <ul className="flex flex-col divide-y divide-border">
        {addresses.map((address) => (
          <li key={address.id} className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                {address.label && <span className="font-semibold" dir="auto">{address.label}</span>}
                <span dir="auto">{line(address)}</span>
                {!address.active && <Badge tone="neutral">{t("inactive")}</Badge>}
              </div>
              <div className="flex flex-wrap gap-2">
                <ButtonLink href={wazeLink(line(address))} target="_blank" rel="noreferrer" variant="secondary" className="text-xs">Waze</ButtonLink>
                <ButtonLink href={googleMapsLink(line(address))} target="_blank" rel="noreferrer" variant="secondary" className="text-xs">Google Maps</ButtonLink>
                {writable && (
                  <form action={setAddressActive.bind(null, clientId, address.id, !address.active)}>
                    <Button type="submit" variant="secondary" aria-label={`${address.active ? t("retire") : t("restore")} - ${line(address)}`} className="text-xs">
                      {address.active ? t("retire") : t("restore")}
                    </Button>
                  </form>
                )}
              </div>
            </div>
            {address.notes && <p dir="auto" className="text-sm text-muted">{address.notes}</p>}
            {writable && (
              <CollapsibleSection variant="inline" title={t("edit")}>
                <div className="pt-3">
                  <AddressForm clientId={clientId} address={address} />
                </div>
              </CollapsibleSection>
            )}
          </li>
        ))}
      </ul>
      {writable && (
        <CollapsibleSection variant="inline" className="rounded-xl bg-subtle p-3" triggerClassName="font-medium text-primary-ink" title={<><Plus aria-hidden="true" className="size-4" /> {t("add")}</>}>
          <div className="pt-3">
            <AddressForm clientId={clientId} />
          </div>
        </CollapsibleSection>
      )}
    </Card>
  );
}
