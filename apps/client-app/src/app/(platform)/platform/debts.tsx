import { router, useFocusEffect } from "expo-router";
import { useCallback } from "react";
import { View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useLocale, useTranslations } from "use-intl";

import { Avatar, BackBar, Badge, ListRow } from "@business-os/app-kit/components/rows";
import { Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { formatMoney } from "@business-os/app-kit/lib/money";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { usePlatform } from "@/providers/platform-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

/** Businesses with an unpaid invoice, the oldest first; a tap opens the business. */
export default function Debts() {
  const t = useTranslations("platform.overdue");
  const tApp = useTranslations("staffApp.debts");
  const locale = useLocale();
  const { api, can } = usePlatform();
  const { palette } = useTheme();
  const allowed = can("billing.manage");

  const load = useCallback(async () => (allowed ? unwrap(await api.GET("/platform/billing/overdue")) : []), [api, allowed]);
  const { data, loading, reload } = useLoad(load);
  useFocusEffect(
    useCallback(() => {
      void reload();
    }, [reload]),
  );

  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium" });
  const back = <BackBar label={tApp("back")} palette={palette} onPress={() => router.back()} />;

  if (!allowed) {
    return (
      <Screen palette={palette}>
        {back}
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{tApp("noPermission")}</Text>
        </Card>
      </Screen>
    );
  }

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      {back}
      <Heading palette={palette}>{t("title")}</Heading>
      {(data ?? []).length === 0 && !loading ? (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("empty")}</Text>
        </Card>
      ) : (
        <View style={{ gap: 8 }}>
          {(data ?? []).map((row) => (
            <ListRow
              key={row.tenant_id}
              palette={palette}
              leading={<Avatar name={row.name} palette={palette} size={36} />}
              title={row.name}
              subtitle={`${formatMoney(row.open_amount, row.currency, locale)} · ${t("since")}: ${date.format(new Date(row.oldest_issued_at))}`}
              trailing={<Badge label={t(`states.${row.billing_state}`)} tone={row.billing_state === "active" ? "primary" : "danger"} palette={palette} />}
              onPress={() => router.push(`/platform/business/${row.tenant_id}`)}
            />
          ))}
        </View>
      )}
    </Screen>
  );
}
