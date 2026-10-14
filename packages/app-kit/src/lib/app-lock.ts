import AsyncStorage from "@react-native-async-storage/async-storage";
import { Platform } from "react-native";

const KEY = "preferences.appLock";

// Loaded lazily: a build made before the native module was added must still start (the lock is
// simply unavailable there) instead of crashing on import.
type LocalAuthentication = typeof import("expo-local-authentication");
function native(): LocalAuthentication | null {
  if (Platform.OS === "web") return null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    return require("expo-local-authentication") as LocalAuthentication;
  } catch {
    return null;
  }
}

/** True when the phone can check Face ID, a fingerprint or the device passcode and the user has set one up. */
export async function isAppLockSupported(): Promise<boolean> {
  const auth = native();
  if (!auth) return false;
  try {
    return (await auth.hasHardwareAsync()) && (await auth.isEnrolledAsync());
  } catch {
    return false;
  }
}

export async function loadAppLock(): Promise<boolean> {
  return (await AsyncStorage.getItem(KEY)) === "1";
}

export async function saveAppLock(on: boolean): Promise<void> {
  await AsyncStorage.setItem(KEY, on ? "1" : "0");
}

/** Asks the phone to verify the user (Face ID / fingerprint, falling back to the device passcode). */
export async function authenticate(promptMessage: string, cancelLabel: string): Promise<boolean> {
  const auth = native();
  if (!auth) return false;
  try {
    const result = await auth.authenticateAsync({ promptMessage, cancelLabel, disableDeviceFallback: false });
    return result.success;
  } catch {
    return false;
  }
}

export { LOCK_AFTER_MS, shouldLock } from "./app-lock-rules";
