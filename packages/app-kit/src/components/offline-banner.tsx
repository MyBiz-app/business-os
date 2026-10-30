import { useEffect } from "react";
import { Platform, Pressable, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslations } from "use-intl";

import { isApiHealthy } from "../lib/api";
import { tint } from "../lib/brand";
import { setOnline, useOnline } from "../lib/connection";
import { fixedColors } from "../lib/theme";
import { useTheme } from "../providers/theme-provider";
import { Text } from "./text";

const RECHECK_MS = 8000;

/** A bar on top of the app while the server cannot be reached: what was loaded stays on screen, and the
 * bar goes by itself when the connection is back. */
export function OfflineBanner() {
  const t = useTranslations("common");
  const { palette } = useTheme();
  const online = useOnline();
  const insets = useSafeAreaInsets();

  useEffect(() => {
    if (Platform.OS !== "web" || typeof window === "undefined") return;
    const down = () => setOnline(false);
    const up = () => void isApiHealthy().then((ok) => ok && setOnline(true));
    window.addEventListener("offline", down);
    window.addEventListener("online", up);
    return () => {
      window.removeEventListener("offline", down);
      window.removeEventListener("online", up);
    };
  }, []);

  useEffect(() => {
    if (online) return;
    const timer = setInterval(() => void isApiHealthy().then((ok) => ok && setOnline(true)), RECHECK_MS);
    return () => clearInterval(timer);
  }, [online]);

  if (online) return null;
  return (
    <View accessibilityRole="alert" style={[styles.bar, { paddingTop: insets.top + 8, borderColor: palette.border, backgroundColor: tint(fixedColors.amber, 0.15) }]}>
      <Text style={[styles.text, { color: palette.foreground }]}>{t("offline")}</Text>
      <Pressable accessibilityRole="button" style={styles.retry} onPress={() => void isApiHealthy().then((ok) => ok && setOnline(true))}>
        <Text style={[styles.link, { color: palette.foreground }]}>{t("retry")}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: { borderBottomWidth: 1, paddingHorizontal: 16, paddingVertical: 8, flexDirection: "row", alignItems: "center", gap: 12 },
  text: { fontSize: 13, flexShrink: 1, flex: 1 },
  retry: { minHeight: 44, justifyContent: "center" },
  link: { fontSize: 13, fontWeight: "500", textDecorationLine: "underline" },
});
