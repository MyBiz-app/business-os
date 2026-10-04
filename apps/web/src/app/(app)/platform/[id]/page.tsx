import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ColumnChart } from "@/components/charts/column-chart";
import { getApi, unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { getActiveMembership } from "@/lib/tenant";

import { openAsSupport } from "../actions";

/** Platform console (P-2): one business's modules and usage. Its own data opens only through
 * support access, which the owner grants for a limited time (read-only and audited). */
export default async function PlatformBusinessPage({ params }: PageProps<"/platform/[id]">) {
  const { id } = await params;
  const t = await getTranslations();
  const locale = await getLocale();
  const { me } = await getActiveMembership();
  if (!me.platform_admin) notFound();
  const api = await getApi();
  const [businesses, usage] = await Promise.all([
    api.GET("/platform/businesses").then(unwrap),
    api.GET("/platform/usage", { params: { query: { tenant_id: id, days: 90 } } }).then(unwrap),
  ]);
  const business = businesses.find((b) => b.id === id);
  if (!business) notFound();
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  const credits = usage.filter((u) => u.meter === "ai_credits");
  const grant = me.support_access.find((g) => g.tenant_id === business.id);

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-6 py-10">
      <Link href="/platform" className="text-sm text-primary underline-offset-4 hover:underline">
        {t("platform.title")}
      </Link>
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold" dir="auto">
          {business.name}
        </h1>
        <p className="text-sm text-muted">
          <span dir="ltr">{business.owner_email}</span> · {business.time_zone} · {business.currency}
        </p>
      </div>
      <section className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-surface p-4">
        {grant ? (
          <>
            <p className="text-sm">
              {t("support.grantedUntil", {
                date: new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(
                  new Date(grant.expires_at),
                ),
              })}
            </p>
            <form action={openAsSupport.bind(null, business.id)}>
              <button type="submit" className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-on-primary">
                {t("support.open")}
              </button>
            </form>
          </>
        ) : (
          <p className="text-sm text-muted">{t("support.notGranted")}</p>
        )}
      </section>
      <dl className="grid gap-3 sm:grid-cols-4">
        {(
          [
            ["members", business.members],
            ["clients", business.clients],
            ["activeClients", business.active_clients],
            ["aiCredits30d", business.ai_credits_30d],
          ] as const
        ).map(([key, value]) => (
          <div key={key} className="flex flex-col gap-1 rounded-2xl border border-border bg-surface p-4">
            <dt className="text-sm text-muted">{t(`platform.columns.${key}`)}</dt>
            <dd className="text-2xl font-semibold">{number.format(value)}</dd>
          </div>
        ))}
      </dl>
      <section className="flex flex-col gap-2 rounded-2xl border border-border bg-surface p-6">
        <h2 className="font-semibold">{t("platform.columns.modules")}</h2>
        <p>
          {business.modules.length === 0
            ? t("platform.coreOnly")
            : business.modules.map((m) => t(`modules.names.${m as "client_app"}`)).join(" · ")}
        </p>
      </section>
      <section className="rounded-2xl border border-border bg-surface p-6">
        {credits.length === 0 ? (
          <p className="text-muted">{t("platform.noUsage")}</p>
        ) : (
          <ColumnChart
            title={t("platform.aiCreditsPerDay")}
            unit={{ kind: "count" }}
            tableLabel={t("dashboard.showTable")}
            headers={[t("platform.day"), t("platform.aiCredits")]}
            columns={credits.map((point) => ({
              key: point.day,
              label: formatDay(point.day, locale, { day: "numeric", month: "numeric" }),
              value: point.quantity,
              display: number.format(point.quantity),
            }))}
          />
        )}
      </section>
    </main>
  );
}
