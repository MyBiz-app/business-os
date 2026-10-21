import { DataTable } from "@/components/ui/data-table";
import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { BRAND } from "@business-os/i18n/brand";

import { BackLink } from "@/components/back-link";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { getTenantFor } from "@/lib/tenant";
import { EmptyState } from "@/components/empty-state";

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
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/sales" label={t("orders.back")} />
      <PageHeader titleId="orders-heading" title={t("orders.title")} description={t("orders.subtitle")} />
      {items.length === 0 ? (
        <EmptyState variant="list">{t("orders.empty")}</EmptyState>
      ) : (
        <>
          <DataTable
            labelledBy="orders-heading"
            rows={items}
            rowKey={(order) => order.id}
            columns={[
              { key: "date", header: t("orders.date"), nowrap: true, cell: (order) => day(order.created_at) },
              {
                key: "client",
                header: t("orders.client"),
                cell: (order) => (
                  <Link dir="auto" href={`/clients/${order.client_id}`} className="underline-offset-4 hover:underline">
                    {order.client_name}
                  </Link>
                ),
              },
              { key: "item", header: t("orders.item"), cell: (order) => <span dir="auto">{order.plan_name}</span> },
              {
                key: "status",
                header: t("orders.status"),
                cell: (order) => (
                  <>
                    {t(`orders.statuses.${order.status}`)}
                    {order.simulated && <span className="text-muted"> · {t("orders.sample")}</span>}
                  </>
                ),
              },
              {
                key: "amount",
                header: t("orders.amount"),
                align: "end",
                nowrap: true,
                className: "font-semibold",
                cell: (order) => <bdi>{formatMoney(order.amount, order.currency, locale)}</bdi>,
              },
            ]}
          />
          <p className="text-sm text-muted">{t("orders.showing", { shown: items.length, total })}</p>
          {total > items.length && shown < MAX && (
            <Link scroll={false} href={`/sales/orders?shown=${shown + STEP}`} className="btn-secondary self-start px-4 py-2 text-sm">
              {t("orders.more")}
            </Link>
          )}
        </>
      )}
    </Container>
  );
}
