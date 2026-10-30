import { Children, useEffect, useId, useRef } from "react";
import {
  Animated,
  Platform,
  RefreshControl,
  ScrollView,
  StyleSheet,
  TextInput,
  type TextInputProps,
  View,
} from "react-native";
import { Text } from "./text";
import { SafeAreaView } from "react-native-safe-area-context";
import { useTranslations } from "use-intl";

import { controlHeight, radius, space } from "@business-os/design-tokens";
import Ionicons from "@expo/vector-icons/Ionicons";

import { FadeIn, PressableScale, useReducedMotion } from "./motion";
import { font } from "../lib/typography";
import type { Palette } from "../lib/theme";
import { Spinner } from "./spinner";

/**
 * Depth, as on the web: cards are flat (a surface and a hairline), so they carry no shadow. Only what
 * floats (a sheet, a toast, a menu) casts one.
 */
export const elevation = {
  floating: { boxShadow: "0px 1px 3px rgba(24, 24, 27, 0.06), 0px 8px 24px rgba(24, 24, 27, 0.1)" },
} as const;

type ButtonProps = {
  label: string;
  onPress: () => void;
  palette: Palette;
  /** `quiet` is a text-only action for a low-priority step; `danger` is outlined, not filled. */
  variant?: "primary" | "secondary" | "danger" | "quiet";
  busy?: boolean;
  disabled?: boolean;
  accessibilityLabel?: string;
};

export function Button({ label, onPress, palette, variant = "primary", busy, disabled, accessibilityLabel }: ButtonProps) {
  const primary = variant === "primary";
  const quiet = variant === "quiet";
  const color = primary ? palette.onPrimary : variant === "danger" ? palette.danger : quiet ? palette.primaryInk : palette.foreground;
  return (
    <PressableScale
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityState={{ disabled: disabled || busy, busy }}
      disabled={disabled || busy}
      onPress={onPress}
      style={[
        styles.button,
        primary
          ? { backgroundColor: palette.primary }
          : quiet
            ? null
            : { borderWidth: 1, borderColor: palette.border, backgroundColor: palette.surface },
        disabled && { opacity: 0.6 },
      ]}
    >
      {busy ? <Spinner color={color} /> : <Text style={[styles.buttonText, { color }]}>{label}</Text>}
    </PressableScale>
  );
}

type FieldProps = TextInputProps & {
  label: string;
  palette: Palette;
  hint?: string;
  /** A problem with this field: shown right under it, and the field's edge turns red. */
  error?: string | null;
  /** "ltr" for emails, phones, codes and numbers: they read and type left to right even in a Hebrew screen. */
  dir?: "ltr";
};

export function Field({ label, palette, hint, error, dir, style, ...inputProps }: FieldProps) {
  const id = useId();
  return (
    <View style={styles.field}>
      <Text nativeID={id} style={[styles.label, { color: palette.foreground }]}>
        {label}
      </Text>
      <TextInput
        accessibilityLabel={label}
        aria-labelledby={id}
        placeholderTextColor={palette.muted}
        style={[
          styles.input,
          { color: palette.foreground, borderColor: error ? palette.danger : palette.border, backgroundColor: palette.surface },
          dir === "ltr" && { writingDirection: "ltr", textAlign: "left" },
          style,
        ]}
        {...inputProps}
      />
      {error ? <ErrorText message={error} palette={palette} /> : hint ? <Text style={[styles.hint, { color: palette.muted }]}>{hint}</Text> : null}
    </View>
  );
}

/** A problem message: a small alert mark and the text in the danger color, the same look as the web's. */
export function ErrorText({ message, palette }: { message?: string | null; palette: Palette }) {
  if (!message) return null;
  return (
    <View style={styles.errorRow}>
      <Ionicons name="alert-circle" size={16} color={palette.danger} style={styles.errorIcon} />
      <Text accessibilityRole="alert" style={[styles.error, { color: palette.danger, flex: 1 }]}>
        {message}
      </Text>
    </View>
  );
}

/** Shown when a screen's data failed to load, so a network error isn't mistaken for "nothing here". */
export function LoadError({ palette, onRetry }: { palette: Palette; onRetry: () => void }) {
  const t = useTranslations("common");
  return (
    <Card palette={palette}>
      <Text accessibilityRole="alert" style={[styles.muted, { color: palette.foreground }]}>
        {t("loadFailed")}
      </Text>
      <Button label={t("retry")} palette={palette} variant="secondary" onPress={onRetry} />
    </Card>
  );
}

type IconName = React.ComponentProps<typeof Ionicons>["name"];

/**
 * An empty list, or a skeleton while the first load runs; keeps every screen's "nothing here" look the
 * same: a quiet icon on a subtle disc, what is missing, an optional hint on what to do, and an optional
 * action (a button the screen passes in).
 */
export function EmptyState({
  palette,
  message,
  hint,
  icon = "file-tray-outline",
  action,
  loading,
}: {
  palette: Palette;
  message: string;
  hint?: string;
  icon?: IconName;
  action?: React.ReactNode;
  loading?: boolean;
}) {
  if (loading) return <SkeletonCard palette={palette} label={message} />;
  return (
    <View style={local.empty}>
      <View aria-hidden style={[local.emptyDisc, { backgroundColor: palette.subtle }]}>
        <Ionicons name={icon} size={24} color={palette.muted} />
      </View>
      <Text accessibilityRole="header" style={[styles.emptyTitle, { color: palette.foreground }]}>
        {message}
      </Text>
      {hint ? <Text style={[styles.hint, { color: palette.muted, textAlign: "center" }]}>{hint}</Text> : null}
      {action ? <View style={local.emptyAction}>{action}</View> : null}
    </View>
  );
}

/** A soft pulsing placeholder block; holds the shape of content while it loads. */
export function Skeleton({ palette, width, height = 14 }: { palette: Palette; width?: number | `${number}%`; height?: number }) {
  const reduced = useReducedMotion();
  const pulse = useRef(new Animated.Value(0.5)).current;
  useEffect(() => {
    if (reduced) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 1, duration: 800, useNativeDriver: Platform.OS !== "web" }),
        Animated.timing(pulse, { toValue: 0.5, duration: 800, useNativeDriver: Platform.OS !== "web" }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [pulse, reduced]);
  return (
    <Animated.View
      aria-hidden
      style={{ width: width ?? "100%", height, borderRadius: Math.min(height / 2, radius.sm), backgroundColor: palette.subtle, opacity: reduced ? 0.7 : pulse }}
    />
  );
}

/** A card-shaped skeleton, announced to screen readers as "loading". */
export function SkeletonCard({ palette, label }: { palette: Palette; label: string }) {
  return (
    <View accessible accessibilityRole="progressbar" accessibilityLabel={label} aria-busy>
      <Card palette={palette}>
        <Skeleton palette={palette} width="40%" height={12} />
        <Skeleton palette={palette} width="75%" height={18} />
        <Skeleton palette={palette} width="55%" height={12} />
      </Card>
    </View>
  );
}

type ScreenProps = {
  palette: Palette;
  children: React.ReactNode;
  refreshing?: boolean;
  onRefresh?: () => void;
  /** A main action pinned above the tab bar (book, pay, save), like a sticky bottom CTA. */
  footer?: React.ReactNode;
  /** A large title that shrinks into a slim bar at the top once the person scrolls (the iOS large-title header). */
  title?: string;
};

/** How far the large title scrolls before the slim bar's title has fully appeared. */
const TITLE_COLLAPSE = 36;

/** A safe-area, scrollable screen with optional pull-to-refresh and an optional large title. */
export function Screen({ palette, children, refreshing, onRefresh, footer, title }: ScreenProps) {
  const scrollY = useRef(new Animated.Value(0)).current;
  const barOpacity = scrollY.interpolate({ inputRange: [0, TITLE_COLLAPSE], outputRange: [0, 1], extrapolate: "clamp" });
  return (
    <SafeAreaView edges={["top", "left", "right"]} style={[styles.screen, { backgroundColor: palette.background }]}>
      {title ? (
        <View style={styles.titleBar} pointerEvents="none">
          <Animated.View style={[StyleSheet.absoluteFill, { backgroundColor: palette.background, opacity: barOpacity }]} />
          <Animated.View style={[styles.titleBarLine, { backgroundColor: palette.border, opacity: barOpacity }]} />
          <Animated.Text
            aria-hidden
            numberOfLines={1}
            style={[styles.titleBarText, { color: palette.foreground, opacity: barOpacity }]}
          >
            {title}
          </Animated.Text>
        </View>
      ) : null}
      <Animated.ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="interactive"
        automaticallyAdjustKeyboardInsets
        scrollEventThrottle={16}
        onScroll={title ? Animated.event([{ nativeEvent: { contentOffset: { y: scrollY } } }], { useNativeDriver: Platform.OS !== "web" }) : undefined}
        refreshControl={onRefresh ? <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} /> : undefined}
      >
        {title ? (
          <Text accessibilityRole="header" style={[styles.largeTitle, { color: palette.foreground }]}>
            {title}
          </Text>
        ) : null}
        {/* Each block of the screen rises in, one after another. */}
        {Children.toArray(children).map((child, index) => (
          <FadeIn key={index} index={index} style={styles.block}>
            {child}
          </FadeIn>
        ))}
      </Animated.ScrollView>
      {footer ? (
        <View style={[styles.footer, { backgroundColor: palette.background, borderTopColor: palette.border }]}>{footer}</View>
      ) : null}
    </SafeAreaView>
  );
}

export function Card({ palette, children }: { palette: Palette; children: React.ReactNode }) {
  return (
    <View style={[styles.card, { backgroundColor: palette.surface, borderColor: palette.border }]}>
      {children}
    </View>
  );
}

export function Heading({ children, palette, level = 1 }: { children: React.ReactNode; palette: Palette; level?: 1 | 2 }) {
  return (
    <Text
      accessibilityRole="header"
      style={[level === 1 ? styles.h1 : styles.h2, { color: palette.foreground }]}
    >
      {children}
    </Text>
  );
}

export const styles = StyleSheet.create({
  screen: { flex: 1 },
  // On a wide browser the content is one centered column, not stretched across the whole window.
  content: { padding: space.lg, gap: space.lg, paddingBottom: space.xxxl + space.sm, width: "100%", maxWidth: 720, alignSelf: "center" },
  block: { gap: space.lg },
  footer: { paddingHorizontal: space.lg, paddingTop: space.md, paddingBottom: space.md, borderTopWidth: StyleSheet.hairlineWidth, gap: space.sm },
  button: { minHeight: controlHeight, borderRadius: radius.control, paddingHorizontal: space.xl, alignItems: "center", justifyContent: "center" },
  buttonText: { fontSize: 15, ...font.medium },
  field: { gap: space.xs + 2 },
  label: { fontSize: 13, ...font.medium, textAlign: "left" },
  // 17px keeps iOS Safari from zooming the page when a field is focused on the web.
  input: { minHeight: controlHeight, borderWidth: 1, borderRadius: radius.control, paddingHorizontal: space.md, fontSize: 17, ...font.regular },
  hint: { fontSize: 13, ...font.regular, textAlign: "left" },
  errorRow: { flexDirection: "row", alignItems: "flex-start", gap: 6 },
  errorIcon: { marginTop: 1 },
  error: { fontSize: 13, ...font.medium, textAlign: "left" },
  // A card is a surface with a hairline; no shadow, and no card inside a card.
  card: { borderWidth: 1, borderRadius: radius.card, padding: space.lg, gap: space.md },
  // The iOS-style large title (30, the top of the Calm scale) and the slim bar it collapses into (17pt, centered, over a hairline).
  largeTitle: { fontSize: 30, lineHeight: 36, ...font.semibold, textAlign: "left" },
  titleBar: { position: "absolute", top: 0, start: 0, end: 0, zIndex: 1, height: 44, alignItems: "center", justifyContent: "center", paddingHorizontal: space.xxxl },
  titleBarLine: { position: "absolute", start: 0, end: 0, bottom: 0, height: StyleSheet.hairlineWidth },
  titleBarText: { fontSize: 17, ...font.semibold },
  h1: { fontSize: 24, lineHeight: 30, ...font.semibold, textAlign: "left" },
  h2: { fontSize: 17, lineHeight: 24, ...font.semibold, textAlign: "left" },
  muted: { fontSize: 15, ...font.regular, textAlign: "left" },
  emptyTitle: { fontSize: 17, lineHeight: 24, ...font.semibold, textAlign: "center" },
});

const local = StyleSheet.create({
  empty: { alignItems: "center", gap: space.sm, paddingVertical: space.xxxl, paddingHorizontal: space.lg },
  emptyDisc: { width: 56, height: 56, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", marginBottom: space.xs },
  emptyAction: { marginTop: space.sm, alignSelf: "stretch", alignItems: "center" },
});
