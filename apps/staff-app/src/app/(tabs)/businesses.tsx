import { useCallback, useState } from "react";
import { Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Card, Field, Heading, Screen, styles } from "@/components/ui";
import { unwrap } from "@/lib/api";
import { useLoad } from "@/lib/use-load";
import { useStaff } from "@/providers/staff-provider";
import { useTheme } from "@/providers/theme-provider";

/** Every business on the platform, searchable. */
export default function Businesses() {
  const t = useTranslations("staffApp.businesses");
  const tModules = useTranslations("modules.names");
  const locale = useLocale();
  const { api } = useStaff();
  const { palette } = useTheme();
  const [search, setSearch] = useState("");

  const load = useCallback(async () => unwrap(await api.GET("/platform/businesses")), [api]);
  const { data, loading, reload } = useLoad(load);
  const number = new Intl.NumberFormat(locale);
  const needle = search.trim().toLowerCase();
  const businesses = (data ?? []).filter(
    (b) => !needle || b.name.toLowerCase().includes(needle) || (b.owner_email ?? "").toLowerCase().includes(needle),
  );

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <Heading palette={palette}>{t("search")}</Heading>
      <Field label={t("search")} palette={palette} value={search} onChangeText={setSearch} autoCapitalize="none" />
      {businesses.length === 0 ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("none")}</Text>
        </Card>
      ) : (
        businesses.slice(0, 50).map((business) => (
          <Card key={business.id} palette={palette}>
            <View style={{ gap: 2 }}>
              <Text style={{ color: palette.foreground, fontWeight: "600" }}>{business.name}</Text>
              <Text style={{ color: palette.muted, fontSize: 13, writingDirection: "ltr" }}>
                {business.owner_email ?? "—"}
              </Text>
              <Text style={{ color: palette.muted, fontSize: 13 }}>
                {t("clients", { count: number.format(business.clients) })}
              </Text>
              <Text style={{ color: palette.muted, fontSize: 13 }}>
                {t("modules")}:{" "}
                {business.modules.length === 0
                  ? "—"
                  : business.modules.map((key) => tModules(key as "client_app")).join(" · ")}
              </Text>
            </View>
          </Card>
        ))
      )}
    </Screen>
  );
}
