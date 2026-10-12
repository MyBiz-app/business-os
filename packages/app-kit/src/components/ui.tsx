import { Children, useId } from "react";
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, TextInput, type TextInputProps, View } from "react-native";
import { Text } from "./text";
import { SafeAreaView } from "react-native-safe-area-context";
import { useTranslations } from "use-intl";

import { FadeIn, PressableScale } from "./motion";
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

type FieldProps = TextInputProps & { label: string; palette: Palette; hint?: string };

export function Field({ label, palette, hint, style, ...inputProps }: FieldProps) {
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
  if (loading) return <ActivityIndicator accessibilityLabel={message} color={palette.primary} />;
  return (
    <Card palette={palette}>
      <Text style={[styles.muted, { color: palette.muted }]}>{message}</Text>
    </Card>
  );
}

type ScreenProps = {
  palette: Palette;
  children: React.ReactNode;
  refreshing?: boolean;
  onRefresh?: () => void;
};

/** A safe-area, scrollable screen with optional pull-to-refresh. */
export function Screen({ palette, children, refreshing, onRefresh }: ScreenProps) {
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
