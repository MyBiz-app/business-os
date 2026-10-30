import { ScrollView, StyleSheet, View } from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";

import { tint } from "../lib/brand";
import { useTheme } from "../providers/theme-provider";
import { elevation } from "./ui";
import { AuthBackdrop } from "./auth-backdrop";
import { FadeIn } from "./motion";
import { ThemeToggle } from "./theme-toggle";
import { radius } from "../lib/theme";

/** The full-screen frame of the sign-in and lock screens: the branded moving backdrop, content
 * centered (it scrolls only when the keyboard or a large text size needs the room), and the
 * theme switch in the corner. */
export function AuthShell({ children, themeToggle = true }: { children: React.ReactNode; themeToggle?: boolean }) {
  const { palette } = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.root, { backgroundColor: palette.background }]}>
      <AuthBackdrop />
      <SafeAreaView edges={["top", "bottom", "left", "right"]} style={styles.fill}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled" keyboardDismissMode="interactive" automaticallyAdjustKeyboardInsets showsVerticalScrollIndicator={false}>
          <View style={styles.column}>{children}</View>
        </ScrollView>
        {/* Outside the ScrollView so the keyboard and tall content never move it. */}
        {themeToggle ? (
          // Absolute children ignore the SafeAreaView padding, so the notch inset is added by hand.
          <View style={[styles.corner, { top: insets.top + 8 }]} pointerEvents="box-none">
            <ThemeToggle size={44} />
          </View>
        ) : null}
      </SafeAreaView>
    </View>
  );
}

/** The glass card the sign-in form sits on. */
export function AuthCard({ children }: { children: React.ReactNode }) {
  const { palette, scheme } = useTheme();
  return (
    <FadeIn
      index={2}
      style={[
        styles.card,
        elevation.floating,
        { backgroundColor: tint(palette.surface, scheme === "dark" ? 0.82 : 0.9), borderColor: tint(palette.border, 0.9) },
      ]}
    >
      {children}
    </FadeIn>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  // Clips the drifting backdrop circles (they start past the edge) so the page never scrolls sideways, in either direction.
  root: { flex: 1, width: "100%", overflow: "hidden" },
  content: { flexGrow: 1, justifyContent: "center", padding: 20 },
  corner: { position: "absolute", end: 12, zIndex: 2 },
  column: { width: "100%", maxWidth: 440, alignSelf: "center", gap: 20, alignItems: "stretch" },
  card: { borderWidth: 1, borderRadius: radius.dialog, padding: 22, gap: 16 },
});
