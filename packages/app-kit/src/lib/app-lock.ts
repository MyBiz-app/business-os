import AsyncStorage from "@react-native-async-storage/async-storage";
import { Platform } from "react-native";

import { DEFAULT_LOCK_TIMEOUT, parseLockTimeout, type LockTimeout } from "./app-lock-rules";

const KEY = "preferences.appLock";
const TIMEOUT_KEY = "preferences.appLockTimeout";
const OFFERED_KEY = "preferences.appLockOffered";

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

/** True once the person chose (on or off) in the settings or on the first-sign-in offer. */
export async function isAppLockDecided(): Promise<boolean> {
  return (await AsyncStorage.getItem(KEY)) !== null;
}

export async function loadLockTimeout(): Promise<LockTimeout> {
  return parseLockTimeout((await AsyncStorage.getItem(TIMEOUT_KEY)) ?? DEFAULT_LOCK_TIMEOUT);
}

export async function saveLockTimeout(timeout: LockTimeout): Promise<void> {
  await AsyncStorage.setItem(TIMEOUT_KEY, timeout);
}

/** Whether the "sign in with Face ID next time?" offer was already shown on this phone. */
export async function wasLockOffered(): Promise<boolean> {
  return (await AsyncStorage.getItem(OFFERED_KEY)) === "1";
}

export async function markLockOffered(): Promise<void> {
  await AsyncStorage.setItem(OFFERED_KEY, "1");
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

export { LOCK_AFTER_MS, LOCK_TIMEOUTS, shouldLock, type LockTimeout } from "./app-lock-rules";
