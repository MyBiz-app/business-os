import { useEffect, useState } from "react";
import { Linking, Pressable, StyleSheet, View } from "react-native";
import { useLocale, useTranslations } from "use-intl";

import { apiClient } from "../lib/api";
import { tint } from "../lib/brand";
import { fixedColors } from "../lib/theme";
import { useTheme } from "../providers/theme-provider";
import { Text } from "./text";

type Banner = { id: string; kind: "incident" | "maintenance" | "security"; title: string; body: string; statusUrl: string };

/** The open incident banners the MyBiz team published (an outage, planned maintenance, a security
 * notice): a bar on top of the app until the team resolves them. Also shown before sign-in. A
 * failure to load them never blocks the app. */
export function IncidentBanner() {
  const t = useTranslations("app.incidentBanner");
  const { palette } = useTheme();
  const locale = useLocale();
  const [items, setItems] = useState<Banner[]>([]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { data } = await apiClient().GET("/public/incidents");
        if (cancelled || !data) return;
        const other = locale === "he" ? "en" : "he";
        setItems(
          data.map((i) => {
            const own = i.content[locale as "he" | "en"];
            const fallback = i.content[other];
            return {
              id: i.id,
              kind: i.kind,
              title: own?.title || fallback?.title || "",
              body: own?.title ? (own.body ?? "") : (fallback?.body ?? ""),
              statusUrl: i.status_url,
            };
          }),
        );
      } catch {
        // the banner is a convenience
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [locale]);

  if (items.length === 0) return null;
  return (
    <View accessibilityRole="alert" style={[styles.bar, { borderColor: palette.border, backgroundColor: tint(fixedColors.amber, 0.15) }]}>
      {items.map((item) => (
        <View key={item.id} style={styles.row}>
          <Text style={[styles.text, { color: palette.foreground }]}>
            {t(`kinds.${item.kind}`)}: {item.title}
            {item.body ? ` - ${item.body}` : ""}
          </Text>
          {item.statusUrl ? (
            <Pressable accessibilityRole="link" onPress={() => void Linking.openURL(item.statusUrl).catch(() => undefined)}>
              <Text style={[styles.link, { color: palette.foreground }]}>{t("status")}</Text>
            </Pressable>
          ) : null}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: { borderBottomWidth: 1, paddingHorizontal: 16, paddingVertical: 8, gap: 6 },
  row: { flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 8 },
  text: { fontSize: 13, flexShrink: 1 },
  link: { fontSize: 13, fontWeight: "500", textDecorationLine: "underline" },
});
