import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Appearance, Platform, useColorScheme } from "react-native";

import { paletteFor, type Palette } from "../lib/theme";
import { loadHighContrast, loadTheme, saveHighContrast, saveTheme, type ThemePreference } from "../lib/preferences";

type ThemeContextValue = {
  preference: ThemePreference;
  setPreference: (preference: ThemePreference) => void;
  scheme: "light" | "dark";
  highContrast: boolean;
  setHighContrast: (on: boolean) => void;
  palette: Palette;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>("system");
  const [highContrast, setHighContrastState] = useState(false);
  const systemScheme = useColorScheme();
  const scheme: "light" | "dark" =
    preference === "system" ? (systemScheme === "dark" ? "dark" : "light") : preference;

  const apply = useCallback((value: ThemePreference) => {
    setPreferenceState(value);
    // Native controls (keyboards, alerts) follow too; not available on the web.
    if (Platform.OS !== "web") Appearance.setColorScheme(value === "system" ? "unspecified" : value);
  }, []);

  useEffect(() => {
    loadTheme().then(apply);
  }, [apply]);

  const setPreference = useCallback(
    (value: ThemePreference) => {
      apply(value);
      void saveTheme(value);
    },
    [apply],
  );

  useEffect(() => {
    loadHighContrast().then(setHighContrastState);
  }, []);

  const setHighContrast = useCallback((on: boolean) => {
    setHighContrastState(on);
    void saveHighContrast(on);
  }, []);

  const value = useMemo(
    () => ({ preference, setPreference, scheme, highContrast, setHighContrast, palette: paletteFor(scheme, highContrast) }),
    [preference, setPreference, scheme, highContrast, setHighContrast],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used inside ThemeProvider");
  return context;
}
