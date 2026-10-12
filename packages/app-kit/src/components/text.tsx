import { textScales } from "@business-os/design-tokens";
import { StyleSheet, Text as NativeText, type TextProps } from "react-native";
import { useLocale } from "use-intl";

import { familyForLocale, scaleText } from "../lib/typography";
import { useOptionalTheme } from "../providers/theme-provider";

/**
 * The app's Text: the same as react-native's, but in the brand fonts. A custom font file is one
 * weight, so the `fontWeight` a style asks for picks the matching file instead (Heebo, or Plus
 * Jakarta Sans for bold English), and every screen gets the brand font without naming it.
 * It also applies the person's text-size setting to the font size and line height.
 */
export function Text({ style, ...props }: TextProps) {
  const locale = useLocale();
  const scale = textScales[useOptionalTheme()?.textSize ?? "normal"];
  const { fontWeight, fontFamily: family, ...rest } = StyleSheet.flatten(style) ?? {};
  return <NativeText {...props} style={[scaleText(rest, scale), { fontFamily: family ?? familyForLocale(fontWeight, locale) }]} />;
}
