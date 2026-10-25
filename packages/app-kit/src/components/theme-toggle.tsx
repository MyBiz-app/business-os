import Ionicons from "@expo/vector-icons/Ionicons";
import { StyleSheet } from "react-native";
import { useTranslations } from "use-intl";

import { PressableScale } from "./motion";
import { tint } from "../lib/brand";
import { useTheme } from "../providers/theme-provider";
import { radius } from "../lib/theme";

/** One-tap sun/moon switch between light and dark (it overrides "follow the system"). */
export function ThemeToggle({ size = 48 }: { size?: number }) {
  const t = useTranslations("settings");
  const { scheme, setPreference, palette } = useTheme();
  const toDark = scheme === "light";
  return (
    <PressableScale
      accessibilityRole="button"
      accessibilityLabel={toDark ? t("themeToggleToDark") : t("themeToggleToLight")}
      onPress={() => setPreference(toDark ? "dark" : "light")}
      style={[styles.button, { width: size, height: size }, { borderColor: palette.border, backgroundColor: tint(palette.primary, 0.08) }]}
    >
      <Ionicons name={toDark ? "moon-outline" : "sunny-outline"} size={size > 40 ? 22 : 18} color={palette.foreground} />
    </PressableScale>
  );
}

const styles = StyleSheet.create({
  button: { width: 48, height: 48, borderRadius: radius.pill, borderWidth: 1, alignItems: "center", justifyContent: "center" },
});
