import Ionicons from "@expo/vector-icons/Ionicons";
import { localeDirection, type Locale } from "@business-os/i18n";
import { minTouch } from "@business-os/design-tokens";
import type { ComponentProps } from "react";
import { type ColorValue, useWindowDimensions, View } from "react-native";
import { useLocale } from "use-intl";

import { tint } from "../lib/brand";
import type { Palette } from "../lib/theme";
import { font } from "../lib/typography";
import { radius } from "../lib/theme";

type IconBase = ComponentProps<typeof Ionicons>["name"] extends infer N
  ? N extends `${infer Base}-outline`
    ? Base
    : never
  : never;

/** From this width up (tablet, desktop web) the tabs move to a side rail. */
const WIDE = 900;

/**
 * A tab icon: outline when idle, filled with a soft pill behind it when it is the current tab,
 * so the current tab is not told apart by color alone.
 */
export const tabIcon = (base: IconBase, palette: Palette) =>
  function TabIcon({ color, focused, size }: { color: ColorValue; focused: boolean; size: number }) {
    const name = (focused ? base : `${base}-outline`) as ComponentProps<typeof Ionicons>["name"];
    return (
      <View
        style={{
          minWidth: 56,
          height: 32,
          borderRadius: radius.dialog,
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: focused ? tint(palette.primary, 0.14) : "transparent",
        }}
      >
        <Ionicons name={name} color={color as string} size={size} />
      </View>
    );
  };

/**
 * Shared look of the bottom tab bar in all three apps: labels always visible, a 48px minimum
 * touch target, 4.5:1 text, and a side rail on wide screens (on the reading-start side, so it
 * follows RTL). Labels grow with the person's text size and wrap rather than get cut.
 */
export function useTabScreenOptions(palette: Palette) {
  const wide = useWindowDimensions().width >= WIDE;
  const rtl = localeDirection[useLocale() as Locale] === "rtl";
  return {
    headerShown: false,
    tabBarShowLabel: true,
    tabBarActiveTintColor: palette.primary,
    tabBarInactiveTintColor: palette.muted,
    tabBarAllowFontScaling: true,
    tabBarLabelStyle: { fontSize: 12, ...font.medium },
    tabBarItemStyle: { minHeight: minTouch, paddingVertical: 4 },
    tabBarStyle: { backgroundColor: palette.surface, borderColor: palette.border, minHeight: wide ? undefined : 64 },
    // Web has no "start" for the rail, only left/right: put it where reading starts.
    ...(wide
      ? { tabBarPosition: rtl ? ("right" as const) : ("left" as const), tabBarVariant: "material" as const }
      : {}),
    sceneStyle: { backgroundColor: palette.background },
  };
}
