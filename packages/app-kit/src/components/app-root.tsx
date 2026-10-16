import { Assistant_400Regular, Assistant_500Medium, Assistant_700Bold } from "@expo-google-fonts/assistant";
import { PlusJakartaSans_700Bold } from "@expo-google-fonts/plus-jakarta-sans";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import type { ComponentType, ReactNode } from "react";

import { displayFontFamily, fontFamily } from "@business-os/design-tokens";
import { I18nProvider } from "../providers/i18n-provider";
import { SessionProvider } from "../providers/session-provider";
import { initMonitoring } from "../lib/monitoring";
import { ThemeProvider, useTheme } from "../providers/theme-provider";
import { AnnouncementsModal } from "./announcements-modal";
import { AppLockGate } from "./app-lock-gate";
import { LaunchSplash } from "./launch-splash";
import { ToastProvider } from "./toast";

initMonitoring();

function ThemedStack() {
  const { scheme, palette } = useTheme();
  return (
    <>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: palette.background } }} />
    </>
  );
}

/** The root every app shares: theme, language, session, then the app's own provider (the
 * business, the client's businesses, or MyBiz staff) around the navigation stack. */
export function AppRoot({ Provider }: { Provider: ComponentType<{ children: ReactNode }> }) {
  // Assistant (Hebrew + Latin) and Plus Jakarta Sans (bold English headings). Screens render with the system font until it is ready, so a slow
  // font download never blocks the app; components opt in through `fontFamily` in the design tokens.
  useFonts({
    [fontFamily.regular]: Assistant_400Regular,
    [fontFamily.medium]: Assistant_500Medium,
    [fontFamily.bold]: Assistant_700Bold,
    [displayFontFamily.bold]: PlusJakartaSans_700Bold,
  });
  return (
    <ThemeProvider>
      <I18nProvider>
        <SessionProvider>
          <Provider>
            <ToastProvider>
              <AppLockGate>
                <ThemedStack />
                <AnnouncementsModal />
              </AppLockGate>
              <LaunchSplash />
            </ToastProvider>
          </Provider>
        </SessionProvider>
      </I18nProvider>
    </ThemeProvider>
  );
}
