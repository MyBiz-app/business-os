import { locales } from "@business-os/i18n";
import { useCallback, useEffect, useState } from "react";
import { RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useTranslations } from "use-intl";

import { SegmentedControl } from "@/components/segmented-control";
import { isApiHealthy } from "@/lib/api";
import type { ThemePreference } from "@/lib/preferences";
import { useLocaleSetting } from "@/providers/i18n-provider";
import { useTheme } from "@/providers/theme-provider";

export default function Home() {
  const t = useTranslations();
  const { palette, preference, setPreference } = useTheme();
  const { locale, setLocale } = useLocaleSetting();
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const checkApi = useCallback(async () => {
    setRefreshing(true);
    setApiOnline(await isApiHealthy());
    setRefreshing(false);
  }, []);

  useEffect(() => {
    void checkApi();
  }, [checkApi]);

  const themeOptions: { value: ThemePreference; label: string }[] = [
    { value: "light", label: t("settings.themeLight") },
    { value: "dark", label: t("settings.themeDark") },
    { value: "system", label: t("settings.themeSystem") },
  ];

  return (
    <SafeAreaView style={[styles.screen, { backgroundColor: palette.background }]}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={checkApi} />}
      >
        <View style={styles.hero}>
          <Text accessibilityRole="header" style={[styles.title, { color: palette.foreground }]}>
            {t("app.name")}
          </Text>
          <Text style={[styles.tagline, { color: palette.muted }]}>{t("app.tagline")}</Text>
        </View>

        <View style={[styles.card, { backgroundColor: palette.surface, borderColor: palette.border }]}>
          <Text style={[styles.cardTitle, { color: palette.muted }]}>{t("home.status")}</Text>
          <View style={styles.statusRow} accessibilityLiveRegion="polite">
            <View
              style={[
                styles.dot,
                { backgroundColor: apiOnline ? palette.success : palette.danger },
                apiOnline === null && { backgroundColor: palette.border },
              ]}
            />
            <Text style={{ color: palette.foreground }}>
              {apiOnline === null ? "…" : apiOnline ? t("home.apiOnline") : t("home.apiOffline")}
            </Text>
          </View>
        </View>

        <SegmentedControl
          label={t("settings.language")}
          options={locales.map((value) => ({ value, label: t(`locales.${value}`) }))}
          value={locale}
          onChange={(value) => void setLocale(value)}
        />

        <SegmentedControl
          label={t("settings.theme")}
          options={themeOptions}
          value={preference}
          onChange={setPreference}
        />

        <Text style={[styles.note, { color: palette.muted }]}>{t("home.comingSoon")}</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1 },
  content: { padding: 24, gap: 24 },
  hero: { gap: 8, paddingTop: 24 },
  title: { fontSize: 34, fontWeight: "700", textAlign: "left" },
  tagline: { fontSize: 17, lineHeight: 24, textAlign: "left" },
  card: { borderWidth: 1, borderRadius: 14, padding: 16, gap: 10 },
  cardTitle: { fontSize: 13, fontWeight: "600", textAlign: "left" },
  statusRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  dot: { width: 10, height: 10, borderRadius: 5 },
  note: { fontSize: 13, textAlign: "left" },
});
