import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

export default async function ServicesPage() {
  const t = await getTranslations();
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("catalog.read");
  const services = unwrap(await api.GET("/services", { params: scope }));

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold">{t("services.title")}</h1>
          <p className="text-sm text-muted">{t("services.subtitle")}</p>
        </div>
        {canWriteCatalog(tenant) && (
          <Link href="/services/new" className="rounded-lg bg-primary px-4 py-2.5 font-semibold text-on-primary">
            {t("services.add")}
          </Link>
        )}
      </div>

      {services.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border p-10 text-center text-muted">{t("services.empty")}</p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {services.map((service) => (
            <li key={service.id}>
              <Link
                href={`/services/${service.id}`}
                className={`flex gap-3 rounded-2xl border border-border bg-surface p-4 hover:border-primary ${service.active ? "" : "opacity-60"}`}
              >
                <span aria-hidden="true" className="mt-1 size-3 shrink-0 rounded-full" style={{ backgroundColor: service.color ?? "var(--primary)" }} />
                <span className="flex flex-1 flex-col gap-1">
                  <span className="flex items-center justify-between gap-2">
                    <span className="font-semibold">{service.name}</span>
                    <span className="text-sm font-medium" dir="ltr">
                      {service.price_amount === 0 ? t("services.free") : formatMoney(service.price_amount, service.price_currency, locale)}
                    </span>
                  </span>
                  <span className="text-sm text-muted">
                    {t("services.minutes", { count: service.duration_minutes })} · {t("services.participants", { count: service.capacity })}
                    {!service.active && ` · ${t("common.inactive")}`}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
