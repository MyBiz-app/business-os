import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ColumnChart } from "@/components/charts/column-chart";
import { getApi, unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { getActiveMembership } from "@/lib/tenant";

/** Platform console (P-1, P-3): every business on the platform and AI usage. */
export default async function PlatformPage() {
  const t = await getTranslations();
  const locale = await getLocale();
  const { me } = await getActiveMembership();
  if (!me.platform_admin) notFound();
  const api = await getApi();
  const [businesses, usage, leads] = await Promise.all([
    api.GET("/platform/businesses").then(unwrap),
    api.GET("/platform/usage", { params: { query: { days: 30 } } }).then(unwrap),
    api.GET("/platform/contact-requests").then(unwrap),
  ]);
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium" });

  // One column per day for the last 30 days (empty days are zero).
  const credits = new Map(usage.filter((u) => u.meter === "ai_credits").map((u) => [u.day, u.quantity]));
  const today = new Date();
  const days = Array.from({ length: 30 }, (_, i) => {
    const day = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate() - 29 + i));
    return day.toISOString().slice(0, 10);
  });
  const totals = {
    businesses: businesses.length,
    activeClients: businesses.reduce((sum, b) => sum + b.active_clients, 0),
    credits: businesses.reduce((sum, b) => sum + b.ai_credits_30d, 0),
    bookings: businesses.reduce((sum, b) => sum + b.bookings_30d, 0),
  };

  return (
    <main className="enter mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-6 py-10">
      <div className="flex flex-col gap-1">
        <h1 className="text-3xl font-bold">{t("platform.title")}</h1>
        <p className="text-sm text-muted">{t("platform.subtitle")}</p>
      </div>

      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {(
          [
            ["businesses", totals.businesses],
            ["activeClients", totals.activeClients],
            ["bookings30d", totals.bookings],
            ["aiCredits30d", totals.credits],
          ] as const
        ).map(([key, value]) => (
          <li key={key} className="flex flex-col gap-1 card p-4">
            <span className="text-sm text-muted">{t(`platform.${key}`)}</span>
            <span className="text-3xl font-semibold">{number.format(value)}</span>
          </li>
        ))}
      </ul>

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

      <section aria-labelledby="businesses-heading" className="flex flex-col gap-3">
        <h2 id="businesses-heading" className="text-lg font-semibold">
          {t("platform.businessesTitle")}
        </h2>
        <div className="overflow-x-auto rounded-2xl border border-border">
          <table className="w-full text-sm">
            <thead className="bg-surface text-muted">
              <tr>
                {(["name", "owner", "modules", "clients", "activeClients", "bookings30d", "aiCredits30d", "created"] as const).map((key) => (
                  <th key={key} scope="col" className="px-3 py-2 text-start font-medium">
                    {t(`platform.columns.${key}`)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {businesses.map((business) => (
                <tr key={business.id} className="border-t border-border">
                  <td className="px-3 py-2">
                    <Link href={`/platform/${business.id}`} className="font-medium text-primary underline-offset-4 hover:underline" dir="auto">
                      {business.name}
                    </Link>
                    <div className="text-xs text-muted">{t(`onboarding.verticals.${business.vertical as "fitness"}`)}</div>
                  </td>
                  <td className="px-3 py-2" dir="ltr">
                    {business.owner_email ?? "—"}
                  </td>
                  <td className="px-3 py-2">
                    {business.modules.length === 0
                      ? t("platform.coreOnly")
                      : business.modules.map((m) => t(`modules.names.${m as "client_app"}`)).join(", ")}
                  </td>
                  <td className="px-3 py-2 tabular-nums">{number.format(business.clients)}</td>
                  <td className="px-3 py-2 tabular-nums">{number.format(business.active_clients)}</td>
                  <td className="px-3 py-2 tabular-nums">{number.format(business.bookings_30d)}</td>
                  <td className="px-3 py-2 tabular-nums">{number.format(business.ai_credits_30d)}</td>
                  <td className="px-3 py-2">{date.format(new Date(business.created_at))}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="leads-heading" className="flex flex-col gap-3">
        <h2 id="leads-heading" className="text-lg font-semibold">
          {t("platform.leads")}
        </h2>
        {leads.length === 0 ? (
          <p className="text-muted">{t("platform.noLeads")}</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {leads.map((lead) => (
              <li key={lead.id} className="card flex flex-col gap-2 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-semibold" dir="auto">
                    {lead.name}
                    {lead.business && <span className="font-normal text-muted"> · {lead.business}</span>}
                  </span>
                  <span className="text-sm text-muted">{date.format(new Date(lead.created_at))}</span>
                </div>
                <p className="flex flex-wrap gap-3 text-sm" dir="ltr">
                  <a href={`mailto:${lead.email}`} className="text-primary underline-offset-4 hover:underline">
                    {lead.email}
                  </a>
                  {lead.phone && <span>{lead.phone}</span>}
                </p>
                {lead.vertical && (
                  <p className="text-sm text-muted">{t(`marketing.contact.verticals.${lead.vertical as "fitness"}`)}</p>
                )}
                {lead.message && (
                  <p className="whitespace-pre-wrap text-sm" dir="auto">
                    {lead.message}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
