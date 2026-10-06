import type { components } from "@business-os/api-client";
import { router } from "expo-router";
import { useCallback, useState } from "react";
import { Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Avatar, ListRow, PillRow } from "@business-os/app-kit/components/rows";
import { Card, Field, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { industryName } from "@business-os/app-kit/lib/vertical";
import { useStaff } from "@/providers/staff-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

type Business = components["schemas"]["PlatformBusiness"];
type Sort = "newest" | "name" | "clients" | "bookings";

const SHOWN = 50;
const ORDER: Record<Sort, (a: Business, b: Business) => number> = {
  newest: (a, b) => b.created_at.localeCompare(a.created_at),
  name: (a, b) => a.name.localeCompare(b.name),
  clients: (a, b) => b.clients - a.clients,
  bookings: (a, b) => b.bookings_30d - a.bookings_30d,
};

/** Every business on the platform: search, sort, and a tap into each one. */
export default function Businesses() {
  const t = useTranslations("staffApp.businesses");
  const tList = useTranslations("platform.list");
  const tRoot = useTranslations();
  const locale = useLocale();
  const { api } = useStaff();
  const { palette } = useTheme();
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<Sort>("newest");

  const load = useCallback(async () => unwrap(await api.GET("/platform/businesses")), [api]);
  const { data, loading, reload } = useLoad(load);
  const number = new Intl.NumberFormat(locale);
  const needle = search.trim().toLowerCase();
  const businesses = (data ?? [])
    .filter((b) => !needle || b.name.toLowerCase().includes(needle) || (b.owner_email ?? "").toLowerCase().includes(needle))
    .sort(ORDER[sort]);

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <View style={{ gap: 2 }}>
        <Heading palette={palette}>{t("back")}</Heading>
        {data && <Text style={[styles.muted, { color: palette.muted }]}>{t("count", { count: businesses.length })}</Text>}
      </View>
      <Field
        label={t("search")}
        placeholder={tList("search")}
        palette={palette}
        value={search}
        onChangeText={setSearch}
        autoCapitalize="none"
      />
      <PillRow<Sort>
        label={tList("sort")}
        palette={palette}
        value={sort}
        onChange={setSort}
        options={(["newest", "name", "clients", "bookings"] as Sort[]).map((value) => ({ value, label: tList(`sorts.${value}`) }))}
      />
      {businesses.length === 0 ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{loading ? "…" : t("none")}</Text>
        </Card>
      ) : (
        <View style={{ gap: 8 }}>
          {businesses.slice(0, SHOWN).map((business) => (
            <ListRow
              key={business.id}
              palette={palette}
              leading={<Avatar name={business.name} palette={palette} />}
              title={business.name}
              subtitle={[
                industryName(tRoot, business.vertical),
                t("row", { clients: number.format(business.clients), modules: business.modules.length }),
                business.owner_email,
              ]
                .filter(Boolean)
                .join(" · ")}
              onPress={() => router.push(`/business/${business.id}`)}
            />
          ))}
        </View>
      )}
    </Screen>
  );
}
