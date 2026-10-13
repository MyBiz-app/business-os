import Ionicons from "@expo/vector-icons/Ionicons";
import { StyleSheet } from "react-native";
import { useTranslations } from "use-intl";

import { PressableScale } from "./motion";
import { tint } from "../lib/brand";
import { useTheme } from "../providers/theme-provider";

/** One-tap sun/moon switch between light and dark (it overrides "follow the system"). */
export function ThemeToggle() {
  const t = useTranslations("settings");
  const { scheme, setPreference, palette } = useTheme();
  const toDark = scheme === "light";
  return (
    <PressableScale
      accessibilityRole="button"
      accessibilityLabel={toDark ? t("themeToggleToDark") : t("themeToggleToLight")}
      onPress={() => setPreference(toDark ? "dark" : "light")}
      style={[styles.button, { borderColor: palette.border, backgroundColor: tint(palette.primary, 0.08) }]}
    >
      <Ionicons name={toDark ? "moon-outline" : "sunny-outline"} size={22} color={palette.foreground} />
    </PressableScale>
  );
}

const styles = StyleSheet.create({
  button: { width: 48, height: 48, borderRadius: 24, borderWidth: 1, alignItems: "center", justifyContent: "center" },
});
