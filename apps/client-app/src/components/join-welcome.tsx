import Ionicons from "@expo/vector-icons/Ionicons";
import { router } from "expo-router";
import type { ComponentProps } from "react";
import { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { Text } from "@business-os/app-kit/components/text";
import { useTranslations } from "use-intl";

import { Button, Card, Heading, Screen, styles } from "@business-os/app-kit/components/ui";
import { radius, type Palette } from "@business-os/app-kit/lib/theme";
import { CancellationPolicyCard } from "@/components/cancellation-policy-card";
import { mustDeclare, useHealth } from "@/lib/use-health";
import { useBusiness } from "@/providers/business-provider";

type Step = { key: string; icon: ComponentProps<typeof Ionicons>["name"]; to: "/health" | "/bookings" | "/schedule" };

/** Right after joining: three short steps instead of a wall of rules; the cancellation policy is one tap away. */
export function JoinWelcome({ name, tenantId, palette }: { name: string; tenantId: string; palette: Palette }) {
  const t = useTranslations("client.join");
  const { business } = useBusiness();
  const health = useHealth();
  const [showPolicy, setShowPolicy] = useState(false);

  const steps: Step[] = [
    ...(mustDeclare(health) ? [{ key: "health", icon: "heart-outline", to: "/health" } as Step] : []),
    ...(business?.online_sales ? [{ key: "plan", icon: "card-outline", to: "/bookings" } as Step] : []),
    { key: "book", icon: "calendar-outline", to: "/schedule" },
  ];

  return (
    <Screen palette={palette}>
      <Heading palette={palette}>{t("joinedTitle", { name })}</Heading>
      <Text style={[styles.muted, { color: palette.muted }]}>{t("joinedBody")}</Text>
      {steps.map((step, index) => (
        <Pressable key={step.key} accessibilityRole="button" accessibilityLabel={t(`step.${step.key}`)} onPress={() => router.replace(step.to)}>
          <Card palette={palette}>
            <View style={local.row}>
              <View style={[local.badge, { backgroundColor: palette.primary }]}>
                <Text style={[local.number, { color: palette.onPrimary }]}>{index + 1}</Text>
              </View>
              <View style={local.text}>
                <Text style={[styles.h2, { color: palette.foreground }]}>{t(`step.${step.key}`)}</Text>
                <Text style={[styles.muted, { color: palette.muted }]}>{t(`stepHint.${step.key}`)}</Text>
              </View>
              <Ionicons name={step.icon} size={22} color={palette.muted} />
            </View>
          </Card>
        </Pressable>
      ))}
      {showPolicy ? (
        <CancellationPolicyCard palette={palette} tenantId={tenantId} />
      ) : (
        <Button label={t("showPolicy")} variant="quiet" palette={palette} onPress={() => setShowPolicy(true)} />
      )}
      <Button label={t("toHome")} variant="secondary" palette={palette} onPress={() => router.replace("/home")} />
    </Screen>
  );
}

const local = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 12 },
  badge: { width: 32, height: 32, borderRadius: radius.pill, alignItems: "center", justifyContent: "center" },
  number: { fontWeight: "600", fontSize: 15 },
  text: { flex: 1, gap: 2 },
});
