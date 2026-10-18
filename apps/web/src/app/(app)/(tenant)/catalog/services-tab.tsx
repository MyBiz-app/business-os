import { CalendarDays, Gauge } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { SummaryTiles } from "@/components/ui/summary-tiles";
import { unwrap } from "@/lib/api";
import { addDays, todayIn } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { canReadReports, canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { catalogHref, type CatalogShow } from "./tabs";

/** The services you offer: tiles that filter, then the cards. Each card opens in a window. */
export async function ServicesTab({ show }: { show: CatalogShow }) {
  const t = await getTranslations();
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("catalog.read");
  // The last 30 days per service, for those who may see reports.
  const end = addDays(todayIn(tenant.time_zone), -1);
  const [all, usage] = await Promise.all([
    api.GET("/services", { params: scope }).then(unwrap),
    canReadReports(tenant)
      ? api
          .GET("/metrics/breakdown/{dimension}", {
            params: { ...scope, path: { dimension: "service" }, query: { start: addDays(end, -29), end } },
          })
          .then(unwrap)
      : Promise.resolve([]),
  ]);
  const services = all.filter((service) => (show === "all" ? true : show === "active" ? service.active : !service.active));
  // An isolated number, so "%" stays on the right side in Hebrew too.
  const percentFormat = new Intl.NumberFormat(locale, { style: "percent" });
  const percent = { format: (value: number) => `⁦${percentFormat.format(value)}⁩` };
  const usageOf = new Map(usage.map((row) => [row.key, row]));
  const sessions = usage.reduce((sum, row) => sum + (row.sessions ?? 0), 0);
  const tile = (key: CatalogShow, value: number, hint?: string) => ({
    key,
    label: t(`catalog.tiles.services.${key}`),
    value,
    hint,
    href: catalogHref("services", key),
    active: show === key,
  });

  return (
    <>
      <SummaryTiles
        label={t("catalog.tiles.label")}
        tiles={[
          tile("all", all.length, canReadReports(tenant) ? t("services.stats.sessions", { count: sessions }) : undefined),
          tile("active", all.filter((service) => service.active).length),
          tile("paused", all.filter((service) => !service.active).length),
        ]}
      />
      {services.length === 0 ? (
        <EmptyState variant="list">
          <span className="flex max-w-md flex-col items-center gap-3">
            <span className="font-semibold text-foreground">{t("catalog.servicesEmpty.title")}</span>
            <span>{t("catalog.servicesEmpty.body")}</span>
            {all.length === 0 && canWriteCatalog(tenant) && (
              <Link href="/catalog/services/new" className="btn-primary px-4 py-2.5">
                {t("catalog.servicesEmpty.cta")}
              </Link>
            )}
          </span>
        </EmptyState>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {services.map((service) => (
            <li key={service.id}>
              <Link
                href={`/catalog/services/${service.id}`}
                scroll={false}
                style={{ "--service": service.color ?? "var(--primary)" } as React.CSSProperties}
                className={`flex h-full flex-col gap-4 card card-hover p-5 ${service.active ? "" : "opacity-60"}`}
              >
                <span className="flex items-start gap-3">
                  <span aria-hidden="true" className="mt-0.5 h-10 w-1.5 shrink-0 rounded-full bg-(--service)" />
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span dir="auto" className="font-semibold">{service.name}</span>
                    <span className="text-sm text-muted">
                      {t("services.minutes", { count: service.duration_minutes })} ·{" "}
                      {service.booking_mode === "appointment"
                        ? t("services.appointmentLabel")
                        : service.booking_mode === "resource"
                          ? t("resources.label")
                          : t("services.participants", { count: service.capacity })}
                      {!service.active && ` · ${t("common.inactive")}`}
                    </span>
                  </span>
                  <span className="text-xl font-bold tabular-nums" dir="ltr">
                    {service.price_amount === 0 ? t("services.free") : formatMoney(service.price_amount, service.price_currency, locale)}
                  </span>
                </span>
                {canReadReports(tenant) && (
                  <span className="mt-auto flex flex-wrap gap-x-4 gap-y-1 border-t border-border pt-3 text-sm text-muted">
                    <span className="inline-flex items-center gap-1.5">
                      <CalendarDays aria-hidden="true" className="size-4" />
                      {t("services.stats.sessions", { count: usageOf.get(service.id)?.sessions ?? 0 })}
                    </span>
                    {usageOf.get(service.id)?.occupancy != null && service.booking_mode === "class" && (
                      <span className="inline-flex items-center gap-1.5">
                        <Gauge aria-hidden="true" className="size-4" />
                        {t("services.stats.occupancy", { value: percent.format((usageOf.get(service.id)?.occupancy ?? 0) / 100) })}
                      </span>
                    )}
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
