import { useEffect, useRef } from "react";
import { Animated, StyleSheet, View } from "react-native";
import { useTranslations } from "use-intl";

import { radius, type Palette } from "../lib/theme";

/** Grey bars shaped like a list of cards, shown on the first look at a screen instead of a spinner. */
export function ListSkeleton({ palette, rows = 4 }: { palette: Palette; rows?: number }) {
  const t = useTranslations("common");
  const pulse = useRef(new Animated.Value(0.55)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 800, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 0.55, duration: 800, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);
  const bar = { backgroundColor: palette.border };
  return (
    <View accessible accessibilityLabel={t("loading")} accessibilityRole="progressbar" style={styles.list}>
      {Array.from({ length: rows }, (_, index) => (
        <Animated.View
          key={index}
          style={[styles.card, { opacity: pulse, backgroundColor: palette.surface, borderColor: palette.border }]}
        >
          <View style={[styles.title, bar]} />
          <View style={[styles.line, bar]} />
          <View style={[styles.line, styles.short, bar]} />
        </Animated.View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  list: { gap: 12 },
  card: { borderWidth: StyleSheet.hairlineWidth, borderRadius: radius.card, padding: 16, gap: 10 },
  title: { height: 16, width: "45%", borderRadius: 6 },
  line: { height: 12, width: "90%", borderRadius: 6 },
  short: { width: "60%" },
});
