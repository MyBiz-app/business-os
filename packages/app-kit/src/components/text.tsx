import { textScales } from "@business-os/design-tokens";
import { Platform, StyleSheet, Text as NativeText, type TextProps } from "react-native";
import { useLocale } from "use-intl";

import { familyForLocale, scaleText, systemWeight } from "../lib/typography";
import { useOptionalTheme } from "../providers/theme-provider";

/**
 * The app's Text: the same as react-native's, but in the brand fonts. A custom font file is one
 * weight, so the `fontWeight` a style asks for picks the matching file instead (Assistant, or Plus
 * Jakarta Sans for bold English), and every screen gets the brand font without naming it.
 * On iPhone it is the system font (SF, which covers Hebrew too) in the matching weight, and no font file
 * is needed; Assistant and Plus Jakarta Sans stay for Android and the web.
 * It also applies the person's text-size setting to the font size and line height.
 */
export function Text({ style, ...props }: TextProps) {
  const locale = useLocale();
  const scale = textScales[useOptionalTheme()?.textSize ?? "normal"];
  const { fontWeight, fontFamily: family, ...rest } = StyleSheet.flatten(style) ?? {};
  const face = Platform.OS === "ios" && !family ? { fontWeight: systemWeight(fontWeight) } : { fontFamily: family ?? familyForLocale(fontWeight, locale) };
  return <NativeText {...props} style={[scaleText(rest, scale), face]} />;
}
