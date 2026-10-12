import AsyncStorage from "@react-native-async-storage/async-storage";

const LOCALE_KEY = "preferences.locale";
const THEME_KEY = "preferences.theme";
const CONTRAST_KEY = "preferences.highContrast";

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

export async function loadHighContrast(): Promise<boolean> {
  return (await AsyncStorage.getItem(CONTRAST_KEY)) === "1";
}

export async function saveHighContrast(on: boolean): Promise<void> {
  await AsyncStorage.setItem(CONTRAST_KEY, on ? "1" : "0");
}
