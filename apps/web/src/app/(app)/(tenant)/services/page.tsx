import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { CalendarDays, Gauge } from "lucide-react";

import { FormNotice } from "@/components/form/form-message";
import { unwrap } from "@/lib/api";
import { addDays, todayIn } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { canReadReports, canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

export default async function ServicesPage({ searchParams }: PageProps<"/services">) {
  const { removed } = await searchParams;
  const t = await getTranslations();
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("catalog.read");
  // The last 30 days per service, for those who may see reports.
  const end = addDays(todayIn(tenant.time_zone), -1);
  const [services, usage] = await Promise.all([
    api.GET("/services", { params: scope }).then(unwrap),
    canReadReports(tenant)
      ? api
          .GET("/metrics/breakdown/{dimension}", {
            params: { ...scope, path: { dimension: "service" }, query: { start: addDays(end, -29), end } },
          })
          .then(unwrap)
      : Promise.resolve([]),
  ]);
  // An isolated number, so "%" stays on the right side in Hebrew too.
  const percentFormat = new Intl.NumberFormat(locale, { style: "percent" });
  const percent = { format: (value: number) => `\u2066${percentFormat.format(value)}\u2069` };
  const usageOf = new Map(usage.map((row) => [row.key, row]));

  return (
    <main className="enter mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-10">
      {(removed === "deleted" || removed === "archived") && <FormNotice message={t(`services.removed.${removed}`)} />}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold">{t("services.title")}</h1>
          <p className="text-sm text-muted">{t("services.subtitle")}</p>
        </div>
        {canWriteCatalog(tenant) && (
          <Link href="/services/new" className="btn-primary px-4 py-2.5">
            {t("services.add")}
          </Link>
        )}
      </div>

      {services.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border p-10 text-center text-muted">{t("services.empty")}</p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {services.map((service) => (
            <li key={service.id}>
              <Link
                href={`/services/${service.id}`}
                style={{ "--service": service.color ?? "var(--primary)" } as React.CSSProperties}
                className={`flex h-full flex-col gap-4 card card-hover p-5 ${service.active ? "" : "opacity-60"}`}
              >
                <span className="flex items-start gap-3">
                  <span aria-hidden="true" className="mt-0.5 h-10 w-1.5 shrink-0 rounded-full bg-(--service)" />
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="font-semibold">{service.name}</span>
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
    </main>
  );
}
