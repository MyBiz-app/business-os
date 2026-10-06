import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import type { ComponentType, ReactNode } from "react";

import { I18nProvider } from "../providers/i18n-provider";
import { SessionProvider } from "../providers/session-provider";
import { ThemeProvider, useTheme } from "../providers/theme-provider";

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
