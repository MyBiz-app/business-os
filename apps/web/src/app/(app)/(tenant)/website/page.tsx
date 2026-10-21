import { getLocale, getTranslations } from "next-intl/server";
import { Lock } from "lucide-react";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { getTenantFor } from "@/lib/tenant";
import { termsOf } from "@business-os/verticals";

import { AddSystemForm } from "./add-system-form";
import { EmbedPanel } from "./embed-panel";
import { InsightsPanel } from "./insights-panel";
import { RespondForm } from "./respond-form";
import { SitePreview } from "./site-preview";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";

const STAGES = ["briefing", "received", "building", "review", "live"] as const;

/** "My website": order a landing page that MyBiz builds, and follow it until it is live. */
export default async function WebsitePage() {
  const t = await getTranslations("website");
  const locale = await getLocale();
  const { api, scope, tenant } = await getTenantFor("business.settings");
  const [state, embed] = await Promise.all([
    api.GET("/website/order", { params: scope }).then(unwrap),
    api.GET("/website/embed", { params: scope }).then(unwrap),
  ]);
  const insights = state.order?.stage === "live" ? await api.GET("/website/insights", { params: scope }).then(unwrap) : undefined;
  const order = state.order;
  const stageIndex = order ? STAGES.indexOf(order.stage) : -1;
  const editable = order?.stage === "briefing" || order?.stage === "received";
  const price = (amount: number) => formatMoney(amount, state.price.currency, locale);

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader title={t("title")} description={t("subtitle")} />

      {!state.with_system && (
        <Card as="section" aria-labelledby="site-system" className="flex flex-col gap-3">
          <h2 id="site-system" className="text-lg font-semibold">{t("system.title")}</h2>
          <p className="text-sm text-muted">{t("system.body")}</p>
          <AddSystemForm label={t("system.add")} />
        </Card>
      )}

      {!order && (
        <Card as="section" aria-labelledby="site-offer" className="grid gap-6 md:grid-cols-2">
          <div className="flex flex-col gap-4">
            <p className="flex items-center gap-2 text-xs font-semibold text-primary-ink">
              <Lock aria-hidden="true" className="size-4" />
              {t("offer.locked")}
            </p>
            <h2 id="site-offer" className="text-lg font-semibold">{t("offer.title")}</h2>
            <p className="text-sm text-muted">{t("offer.body")}</p>
            <p className="text-sm">
              {t("offer.price", { setup: price(state.price.setup), monthly: price(state.price.monthly) })}
            </p>
            <p className="text-xs text-muted">{t("offer.nothingCharged")}</p>
            <ButtonLink href="/website/brief" variant="primary" className="w-fit">{t("offer.start")}</ButtonLink>
          </div>
          <SitePreview name={tenant.name} color={tenant.primary_color ?? null} vertical={termsOf(tenant.vertical)} />
        </Card>
      )}

      {order && (
        <>
          <Card as="section" aria-labelledby="site-status" className="flex flex-col gap-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 id="site-status" className="text-lg font-semibold">{t("status.title")}</h2>
              <Badge tone={order.stage === "live" ? "success" : order.stage === "briefing" ? "neutral" : "primary"} dot>{t(`stages.${order.stage}`)}</Badge>
            </div>
            <ol className="grid gap-2 sm:grid-cols-5">
              {STAGES.map((stage, index) => (
                <li key={stage} aria-current={index === stageIndex ? "step" : undefined} className={`rounded-xl border px-3 py-2 text-sm ${index <= stageIndex ? "border-primary bg-primary-subtle font-medium" : "border-border text-muted"}`}>
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
              <ButtonLink href={order.site_url} target="_blank" rel="noopener noreferrer" dir="ltr" variant="primary" className="w-fit">{t("status.open")}</ButtonLink>
            )}
            {editable && (
              <ButtonLink href="/website/brief" variant="secondary" className="w-fit">
                {order.stage === "briefing" ? t("status.continue") : t("status.edit")}
              </ButtonLink>
            )}
          </Card>

          {order.stage === "review" && (
            <Card as="section" aria-labelledby="site-review" className="flex flex-col gap-3">
              <h2 id="site-review" className="text-lg font-semibold">{t("review.title")}</h2>
              <p className="text-sm text-muted">{t("review.body")}</p>
              {order.approved_at ? <p className="text-sm font-medium">{t("review.approved")}</p> : <RespondForm />}
            </Card>
          )}
        </>
      )}

      {insights && <InsightsPanel insights={insights} />}

      <EmbedPanel contactUrl={embed.contact_form_url} bookingUrl={embed.booking_url} inquiriesEnabled={embed.inquiries_enabled} />
    </Container>
  );
}
