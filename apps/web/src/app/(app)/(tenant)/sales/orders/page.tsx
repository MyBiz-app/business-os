import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { ScrollRegion } from "@/components/scroll-region";
import { unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { getTenantFor } from "@/lib/tenant";

const STEP = 50;
const MAX = 200; // the API's page size cap

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("sales");
  return { title: `${t("orders.title")} · ${BRAND.name}` };
}

/** Clients' online purchases, newest first; "Show more" widens the list a step at a time. */
export default async function OrdersPage({ searchParams }: PageProps<"/sales/orders">) {
  const t = await getTranslations("sales");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("reports.read");
  const shown = Math.min(MAX, Math.max(STEP, Number((await searchParams).shown) || STEP));
  const { items, total } = unwrap(await api.GET("/orders", { params: { ...scope, query: { limit: shown } } }));
  const day = (instant: string) =>
    new Date(instant).toLocaleDateString(locale, { day: "numeric", month: "short", timeZone: tenant.time_zone });

  return (
    <main className="enter mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex flex-col gap-1">
        <h1 id="orders-heading" className="text-3xl font-bold">
          {t("orders.title")}
        </h1>
        <p className="text-muted">{t("orders.subtitle")}</p>
      </div>
      {items.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border p-10 text-center text-muted">{t("orders.empty")}</p>
      ) : (
        <>
          <ScrollRegion labelledBy="orders-heading" className="rounded-2xl border border-border">
            <table className="w-full text-sm">
              <thead className="bg-surface text-muted">
                <tr>
                  {(["date", "client", "item", "status", "amount"] as const).map((key) => (
                    <th key={key} scope="col" className={`px-4 py-3 font-medium ${key === "amount" ? "text-end" : "text-start"}`}>
                      {t(`orders.${key}`)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((order) => (
                  <tr key={order.id} className="border-t border-border transition-colors hover:bg-primary/4">
                    <td className="whitespace-nowrap px-4 py-2.5">{day(order.created_at)}</td>
                    <td className="px-4 py-2.5" dir="auto">
                      <Link href={`/clients/${order.client_id}`} className="underline-offset-4 hover:underline">
                        {order.client_name}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5" dir="auto">{order.plan_name}</td>
                    <td className="px-4 py-2.5">
                      {t(`orders.statuses.${order.status}`)}
                      {order.simulated && <span className="text-muted"> · {t("orders.sample")}</span>}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2.5 text-end font-semibold">
                      <bdi>{formatMoney(order.amount, order.currency, locale)}</bdi>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
          <p className="text-sm text-muted">{t("orders.showing", { shown: items.length, total })}</p>
          {total > items.length && shown < MAX && (
            <Link href={`/sales/orders?shown=${shown + STEP}`} className="btn-secondary self-start px-4 py-2 text-sm">
              {t("orders.more")}
            </Link>
          )}
        </>
      )}
    </main>
  );
}
