import { router, useLocalSearchParams } from "expo-router";
import { useCallback } from "react";
import { StyleSheet, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { Button, Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { tint } from "@business-os/app-kit/lib/brand";
import { formatMoney } from "@business-os/app-kit/lib/money";
import { useLoad } from "@business-os/app-kit/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

/** One of the client's receipts, as a document. */
export default function Receipt() {
  const t = useTranslations("receipts");
  const tScreen = useTranslations("client.receipt");
  const locale = useLocale();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { api, scope, business, palette } = useBusiness();

  const load = useCallback(async () => {
    if (!business || !id) return null;
    return unwrap(await api.GET("/client/receipts/{receipt_id}", { params: { ...scope, path: { receipt_id: id } } }));
  }, [api, scope, business, id]);
  const { data: receipt, loading, reload } = useLoad(load);

  if (!business) return null;
  const issued = receipt
    ? new Intl.DateTimeFormat(locale, { dateStyle: "long", timeZone: business.time_zone }).format(new Date(receipt.issued_at))
    : "";

  return (
    <Screen palette={palette} refreshing={loading} onRefresh={() => void reload()}>
      <Heading palette={palette}>{tScreen("title")}</Heading>
      {receipt && (
        <Card palette={palette}>
          {receipt.simulated && (
            <Text style={[local.sample, { color: palette.foreground, backgroundColor: tint("#b45309", 0.12) }]}>{t("sample")}</Text>
          )}
          <Text style={[local.business, { color: palette.foreground }]}>{receipt.business_name}</Text>
          <Text style={[styles.muted, { color: palette.muted }]}>{t("title", { number: receipt.number })}</Text>
          <View style={[local.divider, { backgroundColor: palette.border }]} />
          <Line label={t("issuedAt")} value={issued} palette={palette} />
          <Line label={t("to")} value={receipt.client_name} palette={palette} />
          <Line label={t("item")} value={receipt.description} palette={palette} />
          <Line label={t("method")} value={t(`methods.${receipt.method}`)} palette={palette} />
          <View style={[local.divider, { backgroundColor: palette.border }]} />
          <View style={local.line}>
            <Text style={[local.totalLabel, { color: palette.foreground }]}>{t("total")}</Text>
            <Text style={[local.total, { color: palette.foreground }]}>{formatMoney(receipt.amount, receipt.currency, locale)}</Text>
          </View>
        </Card>
      )}
      <Button label={tScreen("back")} variant="secondary" palette={palette} onPress={() => (router.canGoBack() ? router.back() : router.replace("/bookings"))} />
    </Screen>
  );
}

function Line({ label, value, palette }: { label: string; value: string; palette: { muted: string; foreground: string } }) {
  return (
    <View style={local.line}>
      <Text style={[styles.muted, { color: palette.muted }]}>{label}</Text>
      <Text style={[local.value, { color: palette.foreground }]}>{value}</Text>
    </View>
  );
}

const local = StyleSheet.create({
  sample: { fontSize: 13, fontWeight: "600", borderRadius: 10, padding: 10, textAlign: "center", overflow: "hidden" },
  business: { fontSize: 22, fontWeight: "800", textAlign: "left" },
  divider: { height: 1, marginVertical: 4 },
  line: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12 },
  value: { fontSize: 15, fontWeight: "600", flexShrink: 1, textAlign: "right" },
  totalLabel: { fontSize: 17, fontWeight: "700" },
  total: { fontSize: 22, fontWeight: "800", fontVariant: ["tabular-nums"] },
});
