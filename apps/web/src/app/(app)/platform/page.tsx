import { ArrowRight } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { ColumnChart } from "@/components/charts/column-chart";
import { unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { getPlatform } from "@/lib/platform";

/** The console's home: the platform in numbers, and what's new — each part for whoever may
 * see it. */
export default async function PlatformPage() {
  const t = await getTranslations();
  const locale = await getLocale();
  const { api, can } = await getPlatform();
  const [businesses, usage, leads] = await Promise.all([
    can("businesses.read") ? api.GET("/platform/businesses").then(unwrap) : null,
    can("usage.read") ? api.GET("/platform/usage", { params: { query: { days: 30 } } }).then(unwrap) : null,
    can("inbox.manage") ? api.GET("/platform/contact-requests").then(unwrap) : null,
  ]);
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium" });

  const credits = new Map((usage ?? []).filter((u) => u.meter === "ai_credits").map((u) => [u.day, u.quantity]));
  const today = new Date();
  const days = Array.from({ length: 30 }, (_, i) => {
    const day = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate() - 29 + i));
    return day.toISOString().slice(0, 10);
  });

  return (
    <main className="enter mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-6 py-10">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold">{t("platform.title")}</h1>
        <p className="text-sm text-muted">{t("platform.subtitle")}</p>
      </div>

      {businesses && (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {(
            [
              ["businesses", businesses.length],
              ["activeClients", businesses.reduce((sum, b) => sum + b.active_clients, 0)],
              ["bookings30d", businesses.reduce((sum, b) => sum + b.bookings_30d, 0)],
              ["aiCredits30d", businesses.reduce((sum, b) => sum + b.ai_credits_30d, 0)],
            ] as const
          ).map(([key, value]) => (
            <li key={key} className="flex flex-col gap-1 card p-4">
              <span className="text-sm text-muted">{t(`platform.${key}`)}</span>
              <span className="text-3xl font-semibold">{number.format(value)}</span>
            </li>
          ))}
        </ul>
      )}

      {usage && (
        <section className="card p-6">
          <ColumnChart
            title={t("platform.aiCreditsPerDay")}
            unit={{ kind: "count" }}
            tableLabel={t("dashboard.showTable")}
            headers={[t("platform.day"), t("platform.aiCredits")]}
            columns={days.map((day) => ({
              key: day,
              label: formatDay(day, locale, { day: "numeric", month: "numeric" }),
              value: credits.get(day) ?? 0,
              display: number.format(credits.get(day) ?? 0),
            }))}
          />
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {businesses && (
          <section aria-labelledby="new-businesses" className="card flex flex-col gap-3 p-6">
            <div className="flex items-center justify-between gap-3">
              <h2 id="new-businesses" className="font-semibold">
                {t("platform.newestBusinesses")}
              </h2>
              <Link href="/platform/businesses" className="flex items-center gap-1 text-sm font-medium text-primary underline-offset-4 hover:underline">
                {t("platform.seeAll")} <ArrowRight aria-hidden="true" className="size-4 rtl:rotate-180" />
              </Link>
            </div>
            <ul className="flex flex-col divide-y divide-border">
              {[...businesses]
                .sort((a, b) => b.created_at.localeCompare(a.created_at))
                .slice(0, 5)
                .map((b) => (
                  <li key={b.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                    <Link href={`/platform/businesses/${b.id}`} dir="auto" className="font-medium text-primary underline-offset-4 hover:underline">
                      {b.name}
                    </Link>
                    <span className="text-muted">{date.format(new Date(b.created_at))}</span>
                  </li>
                ))}
            </ul>
          </section>
        )}
        {leads && (
          <section aria-labelledby="new-requests" className="card flex flex-col gap-3 p-6">
            <div className="flex items-center justify-between gap-3">
              <h2 id="new-requests" className="font-semibold">
                {t("platform.latestRequests")}
              </h2>
              <Link href="/platform/inbox" className="flex items-center gap-1 text-sm font-medium text-primary underline-offset-4 hover:underline">
                {t("platform.seeAll")} <ArrowRight aria-hidden="true" className="size-4 rtl:rotate-180" />
              </Link>
            </div>
            {leads.length === 0 ? (
              <p className="text-sm text-muted">{t("platform.noLeads")}</p>
            ) : (
              <ul className="flex flex-col divide-y divide-border">
                {leads.slice(0, 5).map((lead) => (
                  <li key={lead.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                    <span dir="auto" className="font-medium">
                      {lead.name}
                      {lead.business && <span className="font-normal text-muted"> · {lead.business}</span>}
                    </span>
                    <span className="text-muted">{date.format(new Date(lead.created_at))}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
