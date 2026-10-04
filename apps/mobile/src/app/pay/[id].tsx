import Ionicons from "@expo/vector-icons/Ionicons";
import type { components } from "@business-os/api-client";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Animated, Easing, Platform, StyleSheet, Text, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { useReducedMotion } from "@/components/motion";
import { Button, Card, ErrorText, Heading, Screen, elevation, styles } from "@/components/ui";
import { unwrap } from "@/lib/api";
import { tint } from "@/lib/brand";
import { formatMoney } from "@/lib/money";
import { useLoad } from "@/lib/use-load";
import { useBusiness } from "@/providers/business-provider";

type Paid = components["schemas"]["CheckoutPaid"];

/** How long the simulated payment "processes", so it feels like a real one. */
const PROCESSING_MS = 1400;

/** The payment page for a checkout. With the simulated provider it shows a test card and
 * completes the payment without charging anything; a real provider will send the client to its
 * own secure page instead (the checkout's pay_url). */
export default function Pay() {
  const t = useTranslations("client.pay");
  const locale = useLocale();
  const { id } = useLocalSearchParams<{ id: string }>();
  const { api, scope, business, palette } = useBusiness();
  const reduced = useReducedMotion();
  const [stage, setStage] = useState<"ready" | "processing" | "done">("ready");
  const [paid, setPaid] = useState<Paid | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pop = useRef(new Animated.Value(0)).current;

  const load = useCallback(async () => {
    if (!business || !id) return null;
    return unwrap(await api.GET("/client/checkouts/{checkout_id}", { params: { ...scope, path: { checkout_id: id } } }));
  }, [api, scope, business, id]);
  const { data: checkout } = useLoad(load);

  useEffect(() => {
    if (stage !== "done") return;
    Animated.spring(pop, { toValue: 1, speed: 12, bounciness: 12, useNativeDriver: Platform.OS !== "web" }).start();
  }, [stage, pop]);

  if (!business) return null;
  const amount = checkout ? formatMoney(checkout.amount, checkout.currency, locale) : "";

  const pay = async () => {
    if (!checkout) return;
    setStage("processing");
    setError(null);
    try {
      const [result] = await Promise.all([
        api.POST("/client/checkouts/{checkout_id}/simulate-payment", {
          params: { ...scope, path: { checkout_id: checkout.id } },
        }),
        new Promise((resolve) => setTimeout(resolve, reduced ? 0 : PROCESSING_MS)),
      ]);
      setPaid(unwrap(result));
      setStage("done");
    } catch {
      setError(t("failed"));
      setStage("ready");
    }
  };

  if (stage === "done" && paid) {
    const receiptNumber = paid.entitlement.receipt_number;
    return (
      <Screen palette={palette}>
        <View style={local.done}>
          <Animated.View
            style={[
              local.check,
              { backgroundColor: palette.success, transform: [{ scale: pop.interpolate({ inputRange: [0, 1], outputRange: [0.4, 1] }) }] },
            ]}
          >
            <Ionicons name="checkmark" size={56} color="#ffffff" />
          </Animated.View>
          <Text accessibilityRole="header" accessibilityLiveRegion="polite" style={[local.doneTitle, { color: palette.foreground }]}>
            {t("success")}
          </Text>
          <Text style={[styles.muted, local.center, { color: palette.muted }]}>
            {t("successBody", { plan: paid.entitlement.name })}
          </Text>
          {receiptNumber !== null && (
            <Text style={[local.receiptNumber, { color: palette.foreground }]}>{t("receiptNumber", { number: receiptNumber })}</Text>
          )}
        </View>
        {paid.entitlement.receipt_id && (
          <Button label={t("viewReceipt")} palette={palette} onPress={() => router.replace(`/receipt/${paid.entitlement.receipt_id}`)} />
        )}
        <Button label={t("toMyPlans")} variant="secondary" palette={palette} onPress={() => router.replace("/bookings")} />
      </Screen>
    );
  }

  return (
    <Screen palette={palette}>
      <Heading palette={palette}>{t("title")}</Heading>
      {checkout?.simulated && (
        <View style={[local.banner, { backgroundColor: tint("#b45309", 0.12), borderColor: tint("#b45309", 0.4) }]}>
          <Ionicons name="flask-outline" size={18} color={palette.foreground} />
          <Text style={[local.bannerText, { color: palette.foreground }]}>{t("testMode")}</Text>
        </View>
      )}

      {/* A picture of a test card, not a form: nobody types a real card number here. */}
      <View
        accessible
        accessibilityLabel={`${t("testCard")}: 4242 4242 4242 4242`}
        style={[local.card, elevation.raised, { backgroundColor: palette.primary }]}
      >
        <View aria-hidden style={[local.cardOrb, { backgroundColor: tint("#ffffff", 0.14) }]} />
        <View style={local.cardTop}>
          <Text style={[local.cardLabel, { color: palette.onPrimary }]}>{business.name}</Text>
          <Text style={[local.cardBadge, { color: palette.onPrimary, borderColor: palette.onPrimary }]}>TEST</Text>
        </View>
        <View style={[local.chip, { backgroundColor: tint("#ffffff", 0.55) }]} />
        <Text style={[local.cardNumber, { color: palette.onPrimary }]}>4242  4242  4242  4242</Text>
        <View style={local.cardTop}>
          <Text style={[local.cardLabel, { color: palette.onPrimary }]}>{t("testCard")}</Text>
          <Text style={[local.cardLabel, { color: palette.onPrimary }]}>12/30</Text>
        </View>
      </View>

      {checkout && (
        <Card palette={palette}>
          <View style={local.line}>
            <Text style={[styles.muted, { color: palette.muted }]}>{t("plan")}</Text>
            <Text style={[local.value, { color: palette.foreground }]}>{checkout.plan_name}</Text>
          </View>
          <View style={[local.divider, { backgroundColor: palette.border }]} />
          <View style={local.line}>
            <Text style={[local.totalLabel, { color: palette.foreground }]}>{t("total")}</Text>
            <Text style={[local.total, { color: palette.foreground }]}>{amount}</Text>
          </View>
        </Card>
      )}

      <ErrorText message={error} palette={palette} />
      {stage === "processing" ? (
        <View accessibilityLiveRegion="polite" style={local.processing}>
          <ActivityIndicator color={palette.primary} />
          <Text style={[styles.muted, { color: palette.foreground }]}>{t("processing")}</Text>
        </View>
      ) : (
        <Button label={t("payNow", { amount })} palette={palette} disabled={!checkout} onPress={() => void pay()} />
      )}
      <View style={local.secure}>
        <Ionicons name="lock-closed-outline" size={14} color={palette.muted} />
        <Text style={[local.secureText, { color: palette.muted }]}>{t("secure")}</Text>
      </View>
      {stage === "ready" && (
        <Button label={t("cancel")} variant="secondary" palette={palette} onPress={() => router.back()} />
      )}
    </Screen>
  );
}

const local = StyleSheet.create({
  banner: { flexDirection: "row", alignItems: "center", gap: 8, borderWidth: 1, borderRadius: 14, padding: 12 },
  bannerText: { flex: 1, fontSize: 14, fontWeight: "600", textAlign: "left" },
  card: { borderRadius: 22, padding: 22, gap: 18, overflow: "hidden", aspectRatio: 1.6 },
  cardOrb: { position: "absolute", width: 240, height: 240, borderRadius: 999, top: -110, end: -70 },
  cardTop: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  cardLabel: { fontSize: 14, fontWeight: "600" },
  cardBadge: { fontSize: 11, fontWeight: "800", borderWidth: 1, borderRadius: 6, paddingHorizontal: 6, paddingVertical: 1, letterSpacing: 1 },
  chip: { width: 44, height: 32, borderRadius: 7 },
  cardNumber: { fontSize: 21, fontWeight: "700", letterSpacing: 1.5, writingDirection: "ltr", fontVariant: ["tabular-nums"] },
  line: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 12 },
  value: { fontSize: 16, fontWeight: "600" },
  divider: { height: 1 },
  totalLabel: { fontSize: 17, fontWeight: "700" },
  total: { fontSize: 24, fontWeight: "800", fontVariant: ["tabular-nums"] },
  processing: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 10, minHeight: 48 },
  secure: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6 },
  secureText: { fontSize: 13 },
  done: { alignItems: "center", gap: 12, paddingVertical: 32 },
  check: { width: 96, height: 96, borderRadius: 999, alignItems: "center", justifyContent: "center" },
  doneTitle: { fontSize: 26, fontWeight: "800" },
  center: { textAlign: "center" },
  receiptNumber: { fontSize: 15, fontWeight: "600" },
});
