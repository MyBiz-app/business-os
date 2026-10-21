import type { Metadata } from "next";
import { BRAND } from "@business-os/i18n/brand";
import { categories, vertical } from "@business-os/verticals";
import { getTranslations } from "next-intl/server";

import { BusinessMap, type BusinessMapCity, type MapCategory } from "@/components/branch-map/business-map";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { unwrap } from "@/lib/api";
import { getPlatformFor } from "@/lib/platform";
import { industryTexts } from "@/lib/verticals";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("platform.businessMap");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** One color per top-level industry: spread around the color wheel in the catalog's order, the
 * same lightness so none shouts, and the legend and the table name each one in words too. */
const colorOf = (index: number) => `hsl(${Math.round((index * 137.5) % 360)} 62% 48%)`;

/** The businesses and their clients by city, totals only (no city with fewer than five). */
export default async function PlatformBusinessMapPage() {
  const t = await getTranslations("platform.businessMap");
  const { text } = industryTexts(await getTranslations());
  const { api } = await getPlatformFor("businesses.read");
  const found = unwrap(await api.GET("/platform/metrics/business-map"));

  const top = categories();
  const mapCategories: MapCategory[] = top.map((category, i) => ({
    key: category.key,
    label: text(category.key, "name"),
    color: colorOf(i),
  }));
  // A business's industry can be a sub-category: the map groups them under their category.
  const categoryKey = (key: string | null) => (key ? (vertical(key)?.lineage[0] ?? key) : null);
  const shape = (cities: typeof found.businesses): BusinessMapCity[] =>
    cities.map((city) => {
      const merged = new Map<string | null, number>();
      for (const i of city.industries) merged.set(categoryKey(i.vertical), (merged.get(categoryKey(i.vertical)) ?? 0) + i.total);
      return {
        code: city.city_code,
        name: city.city_name,
        latitude: city.latitude,
        longitude: city.longitude,
        total: city.total,
        industries: [...merged.entries()].map(([key, total]) => ({ key, total })).sort((a, b) => b.total - a.total),
      };
    });

  return (
    <Container as="main" size="wide" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader title={t("title")} description={t("subtitle")} />
      <BusinessMap layers={{ businesses: shape(found.businesses), clients: shape(found.clients) }} categories={mapCategories} minPerCity={found.min_per_city} />
      {found.without_point > 0 && <p className="text-sm text-muted">{t("withoutPoint", { count: found.without_point })}</p>}
    </Container>
  );
}
