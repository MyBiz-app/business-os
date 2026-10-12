import { Heebo_400Regular, Heebo_500Medium, Heebo_700Bold } from "@expo-google-fonts/heebo";
import { useFonts } from "expo-font";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import type { ComponentType, ReactNode } from "react";

import { fontFamily } from "@business-os/design-tokens";
import { I18nProvider } from "../providers/i18n-provider";
import { SessionProvider } from "../providers/session-provider";
import { initMonitoring } from "../lib/monitoring";
import { ThemeProvider, useTheme } from "../providers/theme-provider";

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
  // Heebo (Hebrew + Latin). Screens render with the system font until it is ready, so a slow
  // font download never blocks the app; components opt in through `fontFamily` in the design tokens.
  useFonts({
    [fontFamily.regular]: Heebo_400Regular,
    [fontFamily.medium]: Heebo_500Medium,
    [fontFamily.bold]: Heebo_700Bold,
  });
  return (
    <ThemeProvider>
      <I18nProvider>
        <SessionProvider>
          <Provider>
            <ThemedStack />
          </Provider>
        </SessionProvider>
      </I18nProvider>
    </ThemeProvider>
  );
}
