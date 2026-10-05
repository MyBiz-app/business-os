import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

import { I18nProvider } from "@/providers/i18n-provider";
import { SessionProvider } from "@/providers/session-provider";
import { StaffProvider } from "@/providers/staff-provider";
import { ThemeProvider, useTheme } from "@/providers/theme-provider";

function ThemedStack() {
  const { scheme, palette } = useTheme();
  return (
    <>
      <StatusBar style={scheme === "dark" ? "light" : "dark"} />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: palette.background } }} />
    </>
  );
}

export default function RootLayout() {
  return (
    <ThemeProvider>
      <I18nProvider>
        <SessionProvider>
          <StaffProvider>
            <ThemedStack />
          </StaffProvider>
        </SessionProvider>
      </I18nProvider>
    </ThemeProvider>
  );
}
