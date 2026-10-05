import { Children, useId } from "react";
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  type TextInputProps,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { FadeIn, PressableScale } from "@/components/motion";
import { tint } from "@/lib/brand";
import type { Palette } from "@/lib/theme";

/** Soft layered shadows for raised surfaces (same feel as the web app's cards). */
export const elevation = {
  card: { boxShadow: "0px 1px 2px rgba(24, 24, 40, 0.06), 0px 4px 14px rgba(24, 24, 40, 0.06)" },
  raised: { boxShadow: "0px 2px 4px rgba(24, 24, 40, 0.08), 0px 10px 24px rgba(24, 24, 40, 0.12)" },
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
  button: { minHeight: 48, borderRadius: 14, paddingHorizontal: 16, alignItems: "center", justifyContent: "center" },
  buttonText: { fontSize: 16, fontWeight: "600" },
  field: { gap: 6 },
  label: { fontSize: 14, fontWeight: "600", textAlign: "left" },
  input: { minHeight: 48, borderWidth: 1, borderRadius: 14, paddingHorizontal: 14, fontSize: 17 },
  hint: { fontSize: 13, textAlign: "left" },
  error: { fontSize: 14, textAlign: "left" },
  card: { borderWidth: 1, borderRadius: 20, padding: 16, gap: 10 },
  h1: { fontSize: 28, fontWeight: "700", textAlign: "left" },
  h2: { fontSize: 18, fontWeight: "600", textAlign: "left" },
  muted: { fontSize: 15, textAlign: "left" },
});
