import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { BackLink } from "@/components/back-link";
import { EmptyState } from "@/components/empty-state";
import { InsightsMap } from "@/components/insights-map/insights-map";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { PendingArea, PeriodPicker, PeriodProvider } from "@/components/period-picker";
import { unwrap } from "@/lib/api";
import { formatDay, todayIn } from "@/lib/dates";
import { resolveRange } from "@/lib/range";
import { getTenantFor } from "@/lib/tenant";

const PRESETS = [30, 90, 365] as const;

export default async function InsightsMapPage({ searchParams }: PageProps<"/reports/map">) {
  const t = await getTranslations("insightsMap");
  const tNav = await getTranslations("nav");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("reports.read");
  const query = await searchParams;
  const today = todayIn(tenant.time_zone);
  const chosen = resolveRange(query, today, { presets: PRESETS, fallback: 90 });
  const { start, end } = chosen;

  // The clients belong to the whole business, so the map is for people who work in every branch.
  const found = await api.GET("/metrics/map-insights", { params: { header: { "X-Tenant-Id": scope.header["X-Tenant-Id"] }, query: { start, end } } });
  const locations = unwrap(await api.GET("/locations", { params: { header: { "X-Tenant-Id": scope.header["X-Tenant-Id"] } } }));
  const branches = locations
    .filter((l) => l.active && l.latitude !== null && l.longitude !== null)
    .map((l) => ({ id: l.id, name: l.name, cityCode: l.city_code, latitude: l.latitude as number, longitude: l.longitude as number }));

  return (
    <Container as="main" size="wide" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/reports" label={tNav("reports")} />
      <PeriodProvider>
        <PageHeader
          title={t("title")}
          description={t("subtitle", { from: formatDay(start, locale, { day: "numeric", month: "short" }), to: formatDay(end, locale, { day: "numeric", month: "short" }) })}
          actions={<PeriodPicker presets={PRESETS} value={chosen.key} from={start} to={end} today={today} />}
        />
        <PendingArea className="flex flex-col gap-6">
          {found.data ? (
            <InsightsMap
              areas={found.data.areas.map((a) => ({
                code: a.city_code,
                name: a.city_name,
                latitude: a.latitude,
                longitude: a.longitude,
                clients: a.clients,
                newClients: a.new_clients,
                leads: a.leads,
                leadsWon: a.leads_won,
              }))}
              branches={branches}
              totals={{
                clients: found.data.clients_total,
                clientsWithoutCity: found.data.clients_without_city,
                leads: found.data.leads_total,
                leadsWithoutCity: found.data.leads_without_city,
              }}
              canOpenClients={tenant.permissions.includes("clients.read")}
            />
          ) : (
            <EmptyState variant="list">
              {t("branchOnly")}{" "}
              <Link href="/reports" className="text-primary-ink underline underline-offset-4 hover:no-underline">
                {tNav("reports")}
              </Link>
            </EmptyState>
          )}
        </PendingArea>
      </PeriodProvider>
    </Container>
  );
}
