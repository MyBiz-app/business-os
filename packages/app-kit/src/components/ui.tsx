import { Children, useEffect, useId, useRef } from "react";
import {
  ActivityIndicator,
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

import { FadeIn, PressableScale, useReducedMotion } from "./motion";
import { tint } from "../lib/brand";
import { font } from "../lib/typography";
import type { Palette } from "../lib/theme";

/** Soft layered shadows for raised surfaces (same feel as the web app's cards). */
export const elevation = {
  card: { boxShadow: "0px 1px 2px rgba(17, 24, 39, 0.05), 0px 4px 16px rgba(17, 24, 39, 0.07)" },
  raised: { boxShadow: "0px 2px 4px rgba(17, 24, 39, 0.08), 0px 10px 28px rgba(17, 24, 39, 0.14)" },
} as const;

type ButtonProps = {
  label: string;
  onPress: () => void;
  palette: Palette;
  variant?: "primary" | "secondary" | "danger";
  busy?: boolean;
  disabled?: boolean;
  accessibilityLabel?: string;
};

export function Button({ label, onPress, palette, variant = "primary", busy, disabled, accessibilityLabel }: ButtonProps) {
  const primary = variant === "primary";
  const color = primary ? palette.onPrimary : variant === "danger" ? palette.danger : palette.foreground;
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
          ? { backgroundColor: palette.primary, boxShadow: `0px 6px 16px ${tint(palette.primary, 0.35)}` }
          : { borderWidth: 1, borderColor: palette.border, backgroundColor: palette.surface },
        disabled && { opacity: 0.6 },
      ]}
    >
      {busy ? <ActivityIndicator color={color} /> : <Text style={[styles.buttonText, { color }]}>{label}</Text>}
    </PressableScale>
  );
}

type FieldProps = TextInputProps & {
  label: string;
  palette: Palette;
  hint?: string;
  /** "ltr" for emails, phones, codes and numbers: they read and type left to right even in a Hebrew screen. */
  dir?: "ltr";
};

export function Field({ label, palette, hint, dir, style, ...inputProps }: FieldProps) {
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
          { color: palette.foreground, borderColor: palette.border, backgroundColor: palette.surface },
          dir === "ltr" && { writingDirection: "ltr", textAlign: "left" },
          style,
        ]}
        {...inputProps}
      />
      {hint && <Text style={[styles.hint, { color: palette.muted }]}>{hint}</Text>}
    </View>
  );
}

export function ErrorText({ message, palette }: { message?: string | null; palette: Palette }) {
  if (!message) return null;
  return (
    <Text accessibilityRole="alert" style={[styles.error, { color: palette.danger }]}>
      {message}
    </Text>
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

/** An empty list, or a spinner while the first load runs; keeps every screen's "nothing here" look the same. */
export function EmptyState({ palette, message, loading }: { palette: Palette; message: string; loading?: boolean }) {
  if (loading) return <SkeletonCard palette={palette} label={message} />;
  return (
    <Card palette={palette}>
      <Text style={[styles.muted, { color: palette.muted }]}>{message}</Text>
    </Card>
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
      style={{ width: width ?? "100%", height, borderRadius: height / 2, backgroundColor: tint(palette.muted, 0.22), opacity: reduced ? 0.7 : pulse }}
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
};

/** A safe-area, scrollable screen with optional pull-to-refresh. */
export function Screen({ palette, children, refreshing, onRefresh, footer }: ScreenProps) {
  return (
    <SafeAreaView edges={["top", "left", "right"]} style={[styles.screen, { backgroundColor: palette.background }]}>
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        refreshControl={onRefresh ? <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} /> : undefined}
      >
        {/* Each block of the screen rises in, one after another. */}
        {Children.toArray(children).map((child, index) => (
          <FadeIn key={index} index={index} style={styles.block}>
            {child}
          </FadeIn>
        ))}
      </ScrollView>
      {footer ? (
        <View style={[styles.footer, { backgroundColor: palette.background, borderTopColor: palette.border }]}>{footer}</View>
      ) : null}
    </SafeAreaView>
  );
}

export function Card({ palette, children }: { palette: Palette; children: React.ReactNode }) {
  return (
    <View style={[styles.card, elevation.card, { backgroundColor: palette.surface, borderColor: palette.border }]}>
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
  content: { padding: 20, gap: 16, paddingBottom: 40 },
  block: { gap: 16 },
  footer: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 12, borderTopWidth: StyleSheet.hairlineWidth, gap: 8 },
  button: { minHeight: 52, borderRadius: 999, paddingHorizontal: 24, alignItems: "center", justifyContent: "center" },
  buttonText: { fontSize: 16, ...font.bold },
  field: { gap: 6 },
  label: { fontSize: 14, ...font.medium, textAlign: "left" },
  input: { minHeight: 52, borderWidth: 1, borderRadius: 14, paddingHorizontal: 16, fontSize: 17, ...font.regular },
  hint: { fontSize: 13, ...font.regular, textAlign: "left" },
  error: { fontSize: 14, ...font.medium, textAlign: "left" },
  card: { borderWidth: 1, borderRadius: 20, padding: 18, gap: 10 },
  h1: { fontSize: 28, lineHeight: 34, ...font.bold, textAlign: "left" },
  h2: { fontSize: 20, lineHeight: 26, ...font.bold, textAlign: "left" },
  muted: { fontSize: 15, ...font.regular, textAlign: "left" },
});
