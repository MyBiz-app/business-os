import { StyleSheet, Text as NativeText, type TextProps } from "react-native";

import { familyFor } from "../lib/typography";

/**
 * The app's Text: the same as react-native's, but in Heebo. A custom font file is one weight, so
 * the `fontWeight` a style asks for picks the matching Heebo file instead, and every screen
 * gets the brand font without naming it.
 */
export function Text({ style, ...props }: TextProps) {
  const { fontWeight, fontFamily: family, ...rest } = StyleSheet.flatten(style) ?? {};
  return <NativeText {...props} style={[rest, { fontFamily: family ?? familyFor(fontWeight) }]} />;
}
