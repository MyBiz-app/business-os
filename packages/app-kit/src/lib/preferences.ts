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

const TEXT_SIZE_KEY = "preferences.textSize";
const REDUCE_MOTION_KEY = "preferences.reduceMotion";

export type TextSize = "normal" | "large" | "larger";

export async function loadTextSize(): Promise<TextSize> {
  const value = await AsyncStorage.getItem(TEXT_SIZE_KEY);
  return value === "large" || value === "larger" ? value : "normal";
}

export async function saveTextSize(size: TextSize): Promise<void> {
  await AsyncStorage.setItem(TEXT_SIZE_KEY, size);
}

export async function loadReduceMotion(): Promise<boolean> {
  return (await AsyncStorage.getItem(REDUCE_MOTION_KEY)) === "1";
}

export async function saveReduceMotion(on: boolean): Promise<void> {
  await AsyncStorage.setItem(REDUCE_MOTION_KEY, on ? "1" : "0");
}
