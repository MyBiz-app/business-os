import Ionicons from "@expo/vector-icons/Ionicons";
import { router } from "expo-router";
import { useState } from "react";
import { StyleSheet, View } from "react-native";
import { useTranslations } from "use-intl";

import { AuthCard, AuthShell } from "@business-os/app-kit/components/auth-shell";
import { Text } from "@business-os/app-kit/components/text";
import { Button } from "@business-os/app-kit/components/ui";
import { tint } from "@business-os/app-kit/lib/brand";
import { markIntroSeen } from "@business-os/app-kit/lib/intro";
import { font } from "@business-os/app-kit/lib/typography";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

const SLIDES = [
  { key: "what", icon: "calendar-outline" },
  { key: "join", icon: "qr-code-outline" },
  { key: "stay", icon: "notifications-outline" },
] as const;

/** Three short screens the first time the app opens: what it is, how to join a business, what you get. */
export default function Intro() {
  const t = useTranslations("intro");
  const { palette } = useTheme();
  const [index, setIndex] = useState(0);
  const slide = SLIDES[index] ?? SLIDES[0];
  const last = index === SLIDES.length - 1;
  const finish = () => {
    void markIntroSeen();
    router.replace("/sign-in");
  };
  return (
    <AuthShell themeToggle={false}>
      <AuthCard>
        <View style={[local.badge, { backgroundColor: tint(palette.primary, 0.12) }]} accessible={false}>
          <Ionicons name={slide.icon} size={44} color={palette.primary} />
        </View>
        <Text accessibilityRole="header" accessibilityLiveRegion="polite" style={[local.title, { color: palette.foreground }]}>
          {t(`${slide.key}.title`)}
        </Text>
        <Text style={[local.body, { color: palette.muted }]}>{t(`${slide.key}.body`)}</Text>
        <View style={local.dots} accessible accessibilityLabel={t("step", { current: index + 1, total: SLIDES.length })}>
          {SLIDES.map((s, i) => (
            <View key={s.key} style={[local.dot, { backgroundColor: i === index ? palette.primary : palette.border }]} />
          ))}
        </View>
        <Button label={last ? t("start") : t("next")} palette={palette} onPress={() => (last ? finish() : setIndex(index + 1))} />
        {last ? null : <Button label={t("skip")} variant="quiet" palette={palette} onPress={finish} />}
      </AuthCard>
    </AuthShell>
  );
}

const local = StyleSheet.create({
  badge: { width: 88, height: 88, borderRadius: 44, alignItems: "center", justifyContent: "center", alignSelf: "center" },
  title: { fontSize: 28, ...font.semibold, textAlign: "center" },
  body: { fontSize: 17, ...font.regular, textAlign: "center" },
  dots: { flexDirection: "row", gap: 8, justifyContent: "center", paddingVertical: 4 },
  dot: { width: 8, height: 8, borderRadius: 4 },
});
