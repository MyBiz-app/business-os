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
  error: { fontSize: 13, ...font.medium, textAlign: "left" },
  // A card is a surface with a hairline; no shadow, and no card inside a card.
  card: { borderWidth: 1, borderRadius: radius.card, padding: space.lg, gap: space.md },
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
