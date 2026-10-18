import { getLocale, getTranslations } from "next-intl/server";

import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { getPlatformFor } from "@/lib/platform";

import { OrderCard } from "./order-card";

const COLUMNS = ["briefing", "received", "building", "review", "live"] as const;

/** The website orders board (MyBiz Sites): one column per stage, from the brief being written to live. */
export default async function WebsiteOrdersPage() {
  const t = await getTranslations("platform.websites");
  const locale = await getLocale();
  const { api } = await getPlatformFor("businesses.act");
  const orders = unwrap(await api.GET("/platform/website-orders"));

  return (
    <Container as="main" size="wide" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader title={t("title")} description={t("hint")} />
      {orders.length === 0 ? (
        <EmptyState variant="list">{t("empty")}</EmptyState>
      ) : (
        <div className="grid items-start gap-4 xl:grid-cols-5">
          {COLUMNS.map((stage) => {
            const inStage = orders.filter((order) => order.stage === stage);
            return (
              <section key={stage} aria-labelledby={`col-${stage}`} className="flex min-w-0 flex-col gap-3">
                <h2 id={`col-${stage}`} className="text-sm font-semibold">
                  {t(`stages.${stage}`)} <span className="text-muted">{`(${inStage.length})`}</span>
                </h2>
                {inStage.map((order) => (
                  <OrderCard
                    key={order.id}
                    order={order}
                    price={order.setup_price != null && order.monthly_price != null ? `${formatMoney(order.setup_price, order.currency, locale)} + ${formatMoney(order.monthly_price, order.currency, locale)}` : ""}
                  />
                ))}
              </section>
            );
          })}
        </div>
      )}
    </Container>
  );
}
