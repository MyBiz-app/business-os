import type { components } from "@business-os/api-client";
import { router } from "expo-router";
import { useCallback } from "react";
import { Text } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { BackBar, ListRow } from "@business-os/app-kit/components/rows";
import { Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { formatMoney } from "@business-os/app-kit/lib/money";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Receipt = components["schemas"]["Receipt"];

/** My receipts: every payment I made to this business, newest first; each opens as a document. */
export default function Receipts() {
  const t = useTranslations("receipts");
  const tProfile = useTranslations("client.profile");
  const locale = useLocale();
  const { api, scope, business, palette } = useBusiness();

  const load = useCallback(async () => {
    if (!business) return [] as Receipt[];
    return unwrap(await api.GET("/client/receipts", { params: scope }));
  }, [api, scope, business]);
  const { data, loading, reload } = useLoad(load);
  if (!business) return null;
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: business.time_zone });

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <BackBar label={tProfile("title")} palette={palette} onPress={() => router.back()} />
      <Heading palette={palette}>{tProfile("receipts")}</Heading>
      {data && data.length === 0 && (
        <Card palette={palette}>
          <Text style={[styles.muted, { color: palette.muted }]}>{tProfile("noReceipts")}</Text>
        </Card>
      )}
      {data?.map((receipt) => (
        <ListRow
          key={receipt.id}
          palette={palette}
          title={receipt.description}
          subtitle={`${t("short", { number: receipt.number })} · ${date.format(new Date(receipt.issued_at))}`}
          trailing={<Text style={{ color: palette.foreground, fontWeight: "700" }}>{formatMoney(receipt.amount, receipt.currency, locale)}</Text>}
          onPress={() => router.push(`/receipt/${receipt.id}`)}
        />
      ))}
    </Screen>
  );
}
