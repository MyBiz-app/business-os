import { BRAND } from "@business-os/i18n/brand";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { Platform } from "react-native";

import { apiClient } from "./api";
import { loadLocale } from "./preferences";

const DEVICE_KEY = "security.deviceId";

async function deviceId(): Promise<string> {
  const known = await AsyncStorage.getItem(DEVICE_KEY);
  if (known) return known;
  const fresh = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
  await AsyncStorage.setItem(DEVICE_KEY, fresh);
  return fresh;
}

/** Tells the API which device this is, so a sign-in from a new one is emailed to the person.
 * Safe to call on every launch; never throws. */
export async function registerDevice(): Promise<void> {
  try {
    const stored = await loadLocale();
    const system = Platform.OS === "ios" ? "iOS" : Platform.OS === "android" ? "Android" : "web";
    await apiClient().POST("/me/devices/check", {
      body: { device_id: await deviceId(), label: `${BRAND.name} app on ${system}`, locale: stored === "en" ? "en" : "he" },
    });
  } catch {
    // a failed check must never get in the way of signing in
  }
}
