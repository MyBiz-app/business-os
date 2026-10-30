import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import { apiClient } from "./api";

// Push notification plumbing: ask the phone for permission, get its Expo push token and tell the
// API about it. Nothing sends pushes yet. The token needs the EAS project id (set by `eas init`,
// see docs/guides/mobile-builds.md); until then registration quietly does nothing.

const projectId = (Constants.expoConfig?.extra as { eas?: { projectId?: string } } | undefined)?.eas
  ?.projectId;

/** Pushes can only work on a phone build that has the EAS project id (not on the web). */
export const pushAvailable = Platform.OS !== "web" && Boolean(projectId);

let registered: string | null = null;

/** What the phone says about notifications right now ("undetermined": not asked yet). */
export async function pushPermission(): Promise<"granted" | "denied" | "undetermined"> {
  if (!pushAvailable) return "denied";
  try {
    const { status } = await Notifications.getPermissionsAsync();
    return status === "granted" ? "granted" : status === "denied" ? "denied" : "undetermined";
  } catch {
    return "denied";
  }
}

/** Registers this phone for push. With `ask` false it only registers when the person has
 *  already allowed notifications, so it is safe to call on every sign-in. Never throws. */
export async function registerPushToken({ ask = false } = {}): Promise<string | null> {
  if (Platform.OS === "web" || !projectId) return null;
  try {
    if (Platform.OS === "android") {
      await Notifications.setNotificationChannelAsync("default", {
        name: "default",
        // The lint rule cannot follow expo-notifications 58 re-exports; the enum is there at runtime.
        // eslint-disable-next-line import/namespace
        importance: Notifications.AndroidImportance.DEFAULT,
      });
    }
    let { status } = await Notifications.getPermissionsAsync();
    if (status !== "granted" && ask) status = (await Notifications.requestPermissionsAsync()).status;
    if (status !== "granted") return null;
    const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId });
    await apiClient().PUT("/me/push-tokens", {
      body: { token, platform: Platform.OS === "ios" ? "ios" : "android" },
    });
    registered = token;
    return token;
  } catch {
    return null; // push is a convenience; never block sign-in on it
  }
}

/** Forgets this phone's token on the server (call before signing out). Never throws. */
export async function unregisterPushToken(): Promise<void> {
  if (!registered) return;
  const token = registered;
  registered = null;
  try {
    await apiClient().DELETE("/me/push-tokens", {
      body: { token, platform: Platform.OS === "ios" ? "ios" : "android" },
    });
  } catch {
    // the token is pruned on the server when the phone stops answering
  }
}
