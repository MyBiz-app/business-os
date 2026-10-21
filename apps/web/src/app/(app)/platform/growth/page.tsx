import { getLocale, getTranslations } from "next-intl/server";

import { ColumnChart } from "@/components/charts/column-chart";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { ScrollRegion } from "@/components/scroll-region";
import { unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { getPlatformFor } from "@/lib/platform";

const DAYS = 30;
type StepKey = "started" | "account" | "industry" | "business" | "base" | "extras" | "services" | "summary" | "completed";

/** Growth in the console (go-live GL21): where sign-ups stop, how many businesses are active, and
 * who uses the most messages, space and AI. */
export default async function PlatformGrowthPage() {
  const t = await getTranslations("platform.growth");
  const tPlatform = await getTranslations("platform");
  const locale = await getLocale();
  const { api } = await getPlatformFor("usage.read");
  const query = { params: { query: { days: DAYS } } };
  const [funnel, activity, consumers] = await Promise.all([
    api.GET("/platform/funnel", query).then(unwrap),
    api.GET("/platform/activity", query).then(unwrap),
    api.GET("/platform/top-consumers", query).then(unwrap),
  ]);
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  const megabytes = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  const started = funnel[0]?.visitors ?? 0;
  const today = activity.at(-1);

  return (
    <Container as="main" size="settings" className="enter flex flex-1 flex-col gap-8 py-8 sm:py-10">
      <PageHeader title={t("title")} description={t("hint", { days: DAYS })} />

      <section aria-labelledby="growth-funnel" className="card flex flex-col gap-4 p-6">
        <h2 id="growth-funnel" className="text-lg font-semibold">{t("funnel")}</h2>
        <p className="text-sm text-muted">{t("funnelHint")}</p>
        <ol className="flex flex-col gap-2">
          {funnel.map((step, index) => {
            const share = started > 0 ? Math.round((step.visitors / started) * 100) : 0;
            const before = index > 0 ? funnel[index - 1]!.visitors : null;
            const lost = before !== null && before > step.visitors ? before - step.visitors : 0;
            return (
              <li key={step.key} className="grid grid-cols-[8rem_1fr_auto] items-center gap-3 text-sm">
                <span className="font-medium">{t(`steps.${step.key as StepKey}`)}</span>
                <span className="h-3 rounded-full bg-surface-muted" aria-hidden="true">
                  <span className="block h-3 rounded-full bg-primary" style={{ inlineSize: `${share}%` }} />
                </span>
                <span className="tabular-nums text-end">
                  {number.format(step.visitors)} · {share}%
                  {lost > 0 && <span className="ms-2 text-danger">{t("lost", { count: number.format(lost) })}</span>}
                </span>
              </li>
            );
          })}
        </ol>
      </section>

      <section aria-labelledby="growth-active" className="flex flex-col gap-4">
        <h2 id="growth-active" className="text-lg font-semibold">{t("active")}</h2>
        <dl className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-1 card p-5">
            <dt className="text-sm text-muted">{t("activeToday")}</dt>
            <dd className="text-2xl font-bold tabular-nums">{number.format(today?.active_day ?? 0)}</dd>
          </div>
          <div className="flex flex-col gap-1 card p-5">
            <dt className="text-sm text-muted">{t("activeWeek")}</dt>
            <dd className="text-2xl font-bold tabular-nums">{number.format(today?.active_week ?? 0)}</dd>
          </div>
        </dl>
        <div className="card p-6">
          <ColumnChart
            title={t("activePerDay")}
            unit={{ kind: "count" }}
            tableLabel={t("showTable")}
            headers={[tPlatform("day"), t("activeToday")]}
            columns={activity.map((a) => ({
              key: a.day,
              label: formatDay(a.day, locale, { day: "numeric", month: "numeric" }),
              value: a.active_day,
              display: number.format(a.active_day),
            }))}
          />
        </div>
      </section>

      <section aria-labelledby="growth-consumers" className="flex flex-col gap-4">
        <h2 id="growth-consumers" className="text-lg font-semibold">{t("consumers")}</h2>
        <p className="text-sm text-muted">{t("consumersHint", { days: DAYS })}</p>
        <ScrollRegion labelledBy="growth-consumers" className="card">
          <table className="w-full text-sm">
            <thead className="text-muted">
              <tr className="border-b border-border">
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("columns.business")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("columns.messages")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("columns.storage")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("columns.ai")}</th>
              </tr>
            </thead>
            <tbody>
              {consumers.map((c) => (
                <tr key={c.tenant_id} className="border-b border-border last:border-0">
                  <td className="px-4 py-3" dir="auto">{c.name}</td>
                  <td className="px-4 py-3 text-end tabular-nums">{number.format(c.messages)}</td>
                  <td className="px-4 py-3 text-end tabular-nums">{megabytes.format(c.storage_bytes / 1024 ** 2)} MB</td>
                  <td className="px-4 py-3 text-end tabular-nums">{number.format(c.ai_credits)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      </section>
    </Container>
  );
}
