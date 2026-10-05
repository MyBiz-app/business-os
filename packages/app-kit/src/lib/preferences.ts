import AsyncStorage from "@react-native-async-storage/async-storage";

const LOCALE_KEY = "preferences.locale";
const THEME_KEY = "preferences.theme";

export type ThemePreference = "light" | "dark" | "system";

export async function loadLocale(): Promise<string | null> {
  return AsyncStorage.getItem(LOCALE_KEY);
}

export async function saveLocale(locale: string): Promise<void> {
  await AsyncStorage.setItem(LOCALE_KEY, locale);
}

export async function loadTheme(): Promise<ThemePreference> {
  const value = await AsyncStorage.getItem(THEME_KEY);
  return value === "light" || value === "dark" ? value : "system";
}

export async function saveTheme(theme: ThemePreference): Promise<void> {
  await AsyncStorage.setItem(THEME_KEY, theme);
}
