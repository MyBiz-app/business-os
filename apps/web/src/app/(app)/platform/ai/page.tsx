import { getLocale, getTranslations } from "next-intl/server";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { ScrollRegion } from "@/components/scroll-region";
import { unwrap } from "@/lib/api";
import { isolate } from "@/lib/bidi";
import { formatMoney } from "@/lib/money";
import { getPlatformFor } from "@/lib/platform";

import { ConsoleChat } from "./console-chat";
import { PauseButton } from "./pause-button";
import { MarketReports } from "./reports";
import { AiSettingsForm } from "./settings-form";
import { WebSearchForm } from "./web-search-form";

/** AI in the console: what each business costs against what it pays, which models run, the
 * emergency stop, and MyBiz's own AI helpers. */
export default async function PlatformAiPage() {
  const t = await getTranslations("platform.ai");
  const locale = await getLocale();
  const { api, can } = await getPlatformFor("usage.read");
  const costs = unwrap(await api.GET("/platform/ai/costs", { params: { query: { days: 30 } } }));
  const settings = unwrap(await api.GET("/platform/ai/settings"));
  const connectors = unwrap(await api.GET("/platform/ai/connectors", { params: { query: { days: 30 } } }));
  // The conversation left open last time comes back after a refresh.
  const chats = unwrap(await api.GET("/platform/ai/assistant/conversations"));
  const latest = chats[0]
    ? (await api.GET("/platform/ai/assistant/conversations/{chat_id}", { params: { path: { chat_id: chats[0].id } } })).data
    : undefined;
  const agents = unwrap(await api.GET("/platform/ai/agents"));
  const webSearch = unwrap(await api.GET("/platform/ai/web-search"));
  const stamp = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  const canChange = can("billing.manage");
  const trend = (now: number, before: number) => (before === 0 ? (now === 0 ? "" : "↑") : now > before * 1.2 ? "↑" : now < before * 0.8 ? "↓" : "→");

  return (
    <Container as="main" size="settings" className="enter flex flex-1 flex-col gap-8 py-8 sm:py-10">
      <PageHeader titleId="ai-heading" title={t("title")} description={t("hint")} />

      {settings.kill_all && (
        <p role="alert" className="rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 font-medium text-danger">
          {t("killAllOn")}
        </p>
      )}

      <section aria-labelledby="ai-costs" className="flex flex-col gap-4">
        <h2 id="ai-costs" className="text-lg font-semibold">{t("costs")}</h2>
        <dl className="grid gap-3 sm:grid-cols-3">
          <div className="flex flex-col gap-1 card p-5">
            <dt className="text-sm text-muted">{t("totalCredits")}</dt>
            <dd className="text-2xl font-bold tabular-nums">{number.format(costs.total_credits)}</dd>
          </div>
          <div className="flex flex-col gap-1 card p-5">
            <dt className="text-sm text-muted">{t("previousCredits")}</dt>
            <dd className="text-2xl font-bold tabular-nums">{number.format(costs.previous_total_credits)}</dd>
          </div>
          <div className="flex flex-col gap-1 card p-5">
            <dt className="text-sm text-muted">{t("revenue")}</dt>
            <dd className="flex flex-col text-lg font-bold tabular-nums">
              {costs.revenue.length === 0 ? "-" : costs.revenue.map((r) => <bdi key={r.currency}>{formatMoney(r.revenue_monthly_minor, r.currency, locale)}</bdi>)}
            </dd>
          </div>
        </dl>
        <p className="text-sm text-muted">{t("costsHint")}</p>
        <ScrollRegion labelledBy="ai-costs" className="card">
          <table className="w-full text-sm">
            <thead className="text-muted">
              <tr className="border-b border-border">
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("columns.business")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("columns.credits")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("columns.trend")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("columns.revenue")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("columns.margin")}</th>
                {canChange && <th scope="col" className="px-4 py-3 text-start font-medium">{t("columns.control")}</th>}
              </tr>
            </thead>
            <tbody>
              {costs.businesses.map((b) => (
                <tr key={b.tenant_id} className="border-b border-border last:border-0">
                  <td className="px-4 py-3" dir="auto">
                    {b.name}
                    {b.paused && <span className="ms-2 rounded-full bg-danger/10 px-2 py-0.5 text-xs text-danger">{t("paused")}</span>}
                  </td>
                  <td className="px-4 py-3 text-end tabular-nums">{number.format(b.credits)}</td>
                  <td className="px-4 py-3 text-end" aria-label={t("trendLabel", { before: number.format(b.previous_credits) })}>{trend(b.credits, b.previous_credits)}</td>
                  <td className="px-4 py-3 text-end tabular-nums"><bdi>{b.revenue_monthly_minor ? formatMoney(b.revenue_monthly_minor, b.currency, locale) : "-"}</bdi></td>
                  <td className="px-4 py-3 text-end tabular-nums"><bdi>{b.margin_usd_minor === null ? "-" : formatMoney(b.margin_usd_minor, "USD", locale)}</bdi></td>
                  {canChange && (
                    <td className="px-4 py-3">
                      <PauseButton tenantId={b.tenant_id} name={b.name} paused={b.paused} />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      </section>

      <section aria-labelledby="ai-connectors" className="flex flex-col gap-4">
        <h2 id="ai-connectors" className="text-lg font-semibold">{t("connectors.title")}</h2>
        <p className="text-sm text-muted">{t("connectors.hint")} {t("connectors.limit", { count: connectors.daily_limit })}</p>
        {connectors.businesses.length === 0 ? (
          <p className="card p-5 text-sm text-muted">{t("connectors.empty")}</p>
        ) : (
          <ScrollRegion labelledBy="ai-connectors" className="card">
            <table className="w-full text-sm">
              <thead className="text-muted">
                <tr className="border-b border-border">
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("connectors.columns.business")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("connectors.columns.apps")}</th>
                  <th scope="col" className="px-4 py-3 text-end font-medium">{t("connectors.columns.calls")}</th>
                  <th scope="col" className="px-4 py-3 text-end font-medium">{t("connectors.columns.proposed")}</th>
                  <th scope="col" className="px-4 py-3 text-end font-medium">{t("connectors.columns.executed")}</th>
                  <th scope="col" className="px-4 py-3 text-end font-medium">{t("connectors.columns.rejected")}</th>
                  <th scope="col" className="px-4 py-3 text-end font-medium">{t("connectors.columns.waiting")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("connectors.columns.last")}</th>
                </tr>
              </thead>
              <tbody>
                {connectors.businesses.map((b) => (
                  <tr key={b.tenant_id} className="border-b border-border last:border-0">
                    <td className="px-4 py-3" dir="auto">{b.name}</td>
                    <td className="px-4 py-3" dir="auto">{b.apps.map((app) => isolate(app)).join(", ") || "-"}</td>
                    <td className="px-4 py-3 text-end tabular-nums">{number.format(b.calls)}</td>
                    <td className="px-4 py-3 text-end tabular-nums">{number.format(b.proposed)}</td>
                    <td className="px-4 py-3 text-end tabular-nums">{number.format(b.executed)}</td>
                    <td className="px-4 py-3 text-end tabular-nums">{number.format(b.rejected)}</td>
                    <td className="px-4 py-3 text-end tabular-nums">{number.format(b.waiting)}</td>
                    <td className="px-4 py-3">{b.last_call ? stamp.format(new Date(b.last_call)) : "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
        )}
      </section>

      <section aria-labelledby="ai-models" className="flex flex-col gap-4">
        <h2 id="ai-models" className="text-lg font-semibold">{t("models")}</h2>
        <div className="card p-5">
          <AiSettingsForm
            killAll={settings.kill_all}
            chosen={{ fast: settings.model_fast, standard: settings.model_standard, strong: settings.model_strong }}
            defaults={settings.defaults}
            choices={settings.choices}
            canChange={canChange}
          />
        </div>
      </section>

      <section aria-labelledby="ai-web-search" className="flex flex-col gap-4">
        <h2 id="ai-web-search" className="text-lg font-semibold">{t("webSearch.title")}</h2>
        <p className="text-sm text-muted">{t("webSearch.hint")}</p>
        <div className="card p-5">
          <WebSearchForm enabled={webSearch.enabled} monthlyLimit={webSearch.monthly_limit} used={webSearch.used_this_month} canChange={canChange} />
        </div>
      </section>

      <section aria-labelledby="ai-reports" className="flex flex-col gap-4">
        <h2 id="ai-reports" className="text-lg font-semibold">{t("reports.title")}</h2>
        <p className="text-sm text-muted">{t("reports.hint")}</p>
        <MarketReports />
      </section>

      <section aria-labelledby="ai-team" className="flex flex-col gap-4">
        <h2 id="ai-team" className="text-lg font-semibold">{t("team")}</h2>
        <p className="text-sm text-muted">{t("teamHint")}</p>
        <div className="card p-5">
          <ConsoleChat
            agents={agents}
            canEdit={canChange}
            chats={chats.map((chat) => ({ id: chat.id, role: chat.role, title: chat.title, updatedAt: chat.updated_at }))}
            initial={latest ? { id: latest.id, role: latest.role, turns: latest.turns } : null}
          />
        </div>
      </section>
    </Container>
  );
}
