import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { ScrollRegion } from "@/components/scroll-region";
import { unwrap } from "@/lib/api";
import { getPlatformFor } from "@/lib/platform";

/** Every business on the platform. */
export default async function PlatformBusinessesPage() {
  const t = await getTranslations();
  const locale = await getLocale();
  const { api } = await getPlatformFor("businesses.read");
  const businesses = unwrap(await api.GET("/platform/businesses"));
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium" });

  return (
    <main className="enter mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex flex-col gap-1">
        <h1 id="businesses-heading" className="text-3xl font-bold">
          {t("platform.businessesTitle")}
        </h1>
        <p className="text-sm text-muted">{t("platform.subtitle")}</p>
      </div>
      <ScrollRegion labelledBy="businesses-heading" className="rounded-2xl border border-border">
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
              <tr key={business.id} className="border-t border-border transition-colors hover:bg-primary/4">
                <td className="px-3 py-2">
                  <Link href={`/platform/businesses/${business.id}`} className="font-medium text-primary underline-offset-4 hover:underline" dir="auto">
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
      </ScrollRegion>
    </main>
  );
}
