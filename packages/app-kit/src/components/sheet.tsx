import { motion, radius, space } from "@business-os/design-tokens";
import Ionicons from "@expo/vector-icons/Ionicons";
import { useEffect, useRef, useState } from "react";
import { Animated, Easing, Modal, Platform, Pressable, ScrollView, StyleSheet, useWindowDimensions, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTranslations } from "use-intl";

import { tint } from "../lib/brand";
import { fixedColors, type Palette } from "../lib/theme";
import { useReducedMotion } from "./motion";
import { Text } from "./text";
import { elevation, styles as ui } from "./ui";

const native = Platform.OS !== "web";

type SheetProps = {
  visible: boolean;
  onClose: () => void;
  palette: Palette;
  title: string;
  /** A quiet line under the title (the time of a class, "2 of 3"). */
  subtitle?: string;
  children: React.ReactNode;
  /** Actions pinned under the content (the primary button), outside the scrolling part. */
  footer?: React.ReactNode;
  /** The name of the close button; "Close window" when left out. */
  closeLabel?: string;
};

/**
 * The app's one bottom sheet: a window that rises from the bottom (a centered column on a wide
 * screen) to show a record or a short flow without leaving the list behind it. The scrim fades in on
 * its own while the sheet slides, so the dark layer never rides up with it; both are skipped when the
 * person reduces motion. Esc and the system back gesture close it, like the scrim and the close button.
 */
export function Sheet({ visible, onClose, palette, title, subtitle, children, footer, closeLabel }: SheetProps) {
  const t = useTranslations("common");
  const reduced = useReducedMotion();
  const { height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const progress = useRef(new Animated.Value(0)).current;
  // The modal stays mounted while the sheet slides out.
  const [mounted, setMounted] = useState(visible);

  useEffect(() => {
    if (visible) setMounted(true);
    Animated.timing(progress, {
      toValue: visible ? 1 : 0,
      duration: reduced ? 0 : visible ? motion.slow : motion.base,
      easing: visible ? Easing.out(Easing.cubic) : Easing.in(Easing.cubic),
      useNativeDriver: native,
    }).start(({ finished }) => {
      if (finished && !visible) setMounted(false);
    });
  }, [visible, progress, reduced]);

  if (!mounted) return null;
  const label = closeLabel ?? t("closeDialog");
  return (
    <Modal visible transparent animationType="none" statusBarTranslucent onRequestClose={onClose}>
      <View style={s.root}>
        <Animated.View style={[StyleSheet.absoluteFill, { backgroundColor: tint(fixedColors.black, 0.45), opacity: progress }]}>
          <Pressable style={s.fill} onPress={onClose} accessibilityLabel={label} />
        </Animated.View>
        <Animated.View
          accessibilityViewIsModal
          style={[
            s.sheet,
            elevation.floating,
            {
              backgroundColor: palette.surface,
              borderColor: palette.border,
              maxHeight: height * 0.88,
              paddingBottom: Math.max(insets.bottom, space.lg),
              transform: [{ translateY: progress.interpolate({ inputRange: [0, 1], outputRange: [height, 0] }) }],
            },
          ]}
        >
          <View aria-hidden style={[s.handle, { backgroundColor: palette.border }]} />
          <View style={s.head}>
            <View style={s.title}>
              <Text accessibilityRole="header" style={[ui.h2, { color: palette.foreground }]}>
                {title}
              </Text>
              {subtitle ? <Text style={[ui.hint, { color: palette.muted }]}>{subtitle}</Text> : null}
            </View>
            <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onClose} hitSlop={8} style={s.close}>
              <Ionicons name="close" size={22} color={palette.muted} />
            </Pressable>
          </View>
          <ScrollView style={s.scroll} contentContainerStyle={s.body} keyboardShouldPersistTaps="handled">
            {children}
          </ScrollView>
          {footer ? <View style={s.footer}>{footer}</View> : null}
        </Animated.View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, justifyContent: "flex-end", alignItems: "center" },
  fill: { flex: 1 },
  // A hairline frame and soft floating shadow; only the top corners are round, as it sits on the screen's edge.
  sheet: {
    width: "100%",
    maxWidth: 560,
    borderTopStartRadius: radius.dialog,
    borderTopEndRadius: radius.dialog,
    borderWidth: StyleSheet.hairlineWidth,
    borderBottomWidth: 0,
    paddingHorizontal: space.lg,
    paddingTop: space.sm,
    gap: space.md,
  },
  handle: { alignSelf: "center", width: 36, height: 4, borderRadius: radius.pill },
  head: { flexDirection: "row", alignItems: "flex-start", gap: space.md },
  title: { flex: 1, gap: space.xs },
  close: { width: 32, height: 32, alignItems: "center", justifyContent: "center", borderRadius: radius.pill },
  scroll: { flexGrow: 0 },
  body: { gap: space.md, paddingBottom: space.xs },
  footer: { gap: space.sm },
});
