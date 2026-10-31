import Constants, { ExecutionEnvironment } from "expo-constants";
import { ScrollView, StyleSheet, View } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";

import { tint } from "../lib/brand";
import { useTheme } from "../providers/theme-provider";
import { elevation } from "./ui";
import { AuthBackdrop } from "./auth-backdrop";
import { RevealProvider, useKeyboardReveal } from "./keyboard-scroll";
import { FadeIn } from "./motion";
import { ThemeToggle } from "./theme-toggle";
import { radius } from "../lib/theme";

// Expo Go floats its own round tools button in the top corner; the theme switch sits below it there.
const inExpoGo = Constants.executionEnvironment === ExecutionEnvironment.StoreClient;

/** The full-screen frame of the sign-in and lock screens: the branded moving backdrop, content
 * centered (it scrolls only when the keyboard or a large text size needs the room, and the field
 * being typed in always stays above the keyboard), and the theme switch in the corner. */
export function AuthShell({ children, themeToggle = true }: { children: React.ReactNode; themeToggle?: boolean }) {
  const { palette } = useTheme();
  const insets = useSafeAreaInsets();
  const keyboard = useKeyboardReveal();
  return (
    <View style={[styles.root, { backgroundColor: palette.background }]}>
      <AuthBackdrop />
      <SafeAreaView edges={["top", "bottom", "left", "right"]} style={styles.fill}>
        <ScrollView
          ref={keyboard.scrollRef}
          contentContainerStyle={[styles.content, keyboard.bottomPadding > 0 && { paddingBottom: keyboard.bottomPadding + 20 }]}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="interactive"
          showsVerticalScrollIndicator={false}
          {...keyboard.scrollProps}
        >
          <RevealProvider value={keyboard.reveal}>
            <View style={styles.column}>{children}</View>
          </RevealProvider>
        </ScrollView>
        {/* Outside the ScrollView so the keyboard and tall content never move it. */}
        {themeToggle ? (
          // Absolute children ignore the SafeAreaView padding, so the notch inset is added by hand.
          <View style={[styles.corner, { top: insets.top + (inExpoGo ? 64 : 8) }]} pointerEvents="box-none">
            <ThemeToggle size={44} />
          </View>
        ) : null}
      </SafeAreaView>
    </View>
  );
}

/** The frosted-glass card the sign-in form sits on: translucent so the glows behind show through,
 * a hairline edge and a thin light along its top rim. */
export function AuthCard({ children }: { children: React.ReactNode }) {
  const { palette, scheme } = useTheme();
  const dark = scheme === "dark";
  return (
    <FadeIn
      index={2}
      style={[
        styles.card,
        elevation.floating,
        {
          backgroundColor: tint(palette.surface, dark ? 0.62 : 0.78),
          borderColor: dark ? "rgba(255, 255, 255, 0.12)" : tint(palette.border, 0.9),
        },
      ]}
    >
      <View style={[styles.rim, { backgroundColor: dark ? "rgba(255, 255, 255, 0.28)" : "rgba(255, 255, 255, 0.95)" }]} pointerEvents="none" />
      {children}
    </FadeIn>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  // Clips the drifting backdrop glows (they start past the edge) so the page never scrolls sideways, in either direction.
  root: { flex: 1, width: "100%", overflow: "hidden" },
  content: { flexGrow: 1, justifyContent: "center", padding: 20 },
  corner: { position: "absolute", end: 12, zIndex: 2 },
  column: { width: "100%", maxWidth: 440, alignSelf: "center", gap: 24, alignItems: "stretch" },
  card: { borderWidth: 1, borderRadius: radius.dialog, padding: 22, gap: 16, overflow: "hidden" },
  rim: { position: "absolute", top: 0, start: 28, end: 28, height: 1 },
});
