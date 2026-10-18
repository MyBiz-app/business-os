import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { getTenantFor } from "@/lib/tenant";

import { RespondForm } from "./respond-form";

const STAGES = ["briefing", "received", "building", "review", "live"] as const;

/** "My website": order a landing page that MyBiz builds, and follow it until it is live. */
export default async function WebsitePage() {
  const t = await getTranslations("website");
  const locale = await getLocale();
  const { api, scope } = await getTenantFor("business.settings");
  const state = unwrap(await api.GET("/website/order", { params: scope }));
  const order = state.order;
  const stageIndex = order ? STAGES.indexOf(order.stage) : -1;
  const editable = order?.stage === "briefing" || order?.stage === "received";
  const price = (amount: number) => formatMoney(amount, state.price.currency, locale);

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader title={t("title")} description={t("subtitle")} />

      {!order && (
        <section className="card flex flex-col gap-4 p-6" aria-labelledby="site-offer">
          <h2 id="site-offer" className="text-lg font-semibold">{t("offer.title")}</h2>
          <p className="text-sm text-muted">{t("offer.body")}</p>
          <p className="text-sm">
            {t("offer.price", { setup: price(state.price.setup), monthly: price(state.price.monthly) })}
          </p>
          <p className="text-xs text-muted">{t("offer.nothingCharged")}</p>
          <Link href="/website/brief" className="btn-plain btn-primary w-fit px-4 py-2.5">{t("offer.start")}</Link>
        </section>
      )}

      {order && (
        <>
          <section className="card flex flex-col gap-5 p-6" aria-labelledby="site-status">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="site-status" className="text-lg font-semibold">{t("status.title")}</h2>
              <Pill tone={order.stage === "live" ? "success" : order.stage === "briefing" ? "muted" : "primary"}>{t(`stages.${order.stage}`)}</Pill>
            </div>
            <ol className="grid gap-2 sm:grid-cols-5">
              {STAGES.map((stage, index) => (
                <li key={stage} aria-current={index === stageIndex ? "step" : undefined} className={`rounded-xl border px-3 py-2 text-sm ${index <= stageIndex ? "border-primary bg-primary/10 font-medium" : "border-border text-muted"}`}>
                  {t(`stages.${stage}`)}
                </li>
              ))}
            </ol>
            <p className="text-sm text-muted">{t(`stageHint.${order.stage}`)}</p>
            {order.submitted_at && (
              <p className="text-xs text-muted">{t("status.submitted", { date: formatDay(order.submitted_at.slice(0, 10), locale, { day: "numeric", month: "long", year: "numeric" }) })}</p>
            )}
            {order.setup_price != null && order.monthly_price != null && (
              <p className="text-xs text-muted">{t("status.prices", { setup: price(order.setup_price), monthly: price(order.monthly_price) })}</p>
            )}
            {order.customer_message && (
              <div className="rounded-xl border border-border bg-surface p-3 text-sm">
                <p className="text-xs font-medium text-muted">{t("status.message")}</p>
                <p dir="auto" className="whitespace-pre-line">{order.customer_message}</p>
              </div>
            )}
            {order.change_request && (
              <div className="rounded-xl border border-border bg-surface p-3 text-sm">
                <p className="text-xs font-medium text-muted">{t("status.yourRequest")}</p>
                <p dir="auto" className="whitespace-pre-line">{order.change_request}</p>
              </div>
            )}
            {order.stage === "live" && order.site_url && (
              <a href={order.site_url} target="_blank" rel="noopener noreferrer" dir="ltr" className="btn-plain btn-primary w-fit px-4 py-2.5">{t("status.open")}</a>
            )}
            {editable && (
              <Link href="/website/brief" className="btn-plain btn-secondary w-fit px-4 py-2.5">
                {order.stage === "briefing" ? t("status.continue") : t("status.edit")}
              </Link>
            )}
          </section>

          {order.stage === "review" && (
            <section className="card flex flex-col gap-3 p-6" aria-labelledby="site-review">
              <h2 id="site-review" className="text-lg font-semibold">{t("review.title")}</h2>
              <p className="text-sm text-muted">{t("review.body")}</p>
              {order.approved_at ? <p className="text-sm font-medium">{t("review.approved")}</p> : <RespondForm />}
            </section>
          )}
        </>
      )}
    </Container>
  );
}
