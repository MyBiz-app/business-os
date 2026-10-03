import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Appearance, useColorScheme } from "react-native";

import { colors, type Palette } from "@/lib/theme";
import { loadTheme, saveTheme, type ThemePreference } from "@/lib/preferences";

type ThemeContextValue = {
  preference: ThemePreference;
  setPreference: (preference: ThemePreference) => void;
  scheme: "light" | "dark";
  palette: Palette;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [preference, setPreferenceState] = useState<ThemePreference>("system");
  const systemScheme = useColorScheme();
  const scheme: "light" | "dark" = systemScheme === "dark" ? "dark" : "light";

  const apply = useCallback((value: ThemePreference) => {
    setPreferenceState(value);
    Appearance.setColorScheme(value === "system" ? "unspecified" : value);
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

  const value = useMemo(
    () => ({ preference, setPreference, scheme, palette: colors[scheme] }),
    [preference, setPreference, scheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme must be used inside ThemeProvider");
  return context;
}
