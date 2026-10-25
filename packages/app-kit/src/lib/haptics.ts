import * as Haptics from "expo-haptics";
import { Platform } from "react-native";

const native = Platform.OS !== "web";

const run = (fn: () => Promise<void>) => {
  if (native) void fn().catch(() => undefined);
};

/** Small taps for the phone's haptic engine; every call is a no-op on the web and never throws. */
export const haptics = {
  /** A light tap: opening a sheet, long press picked up. */
  tap: () => run(() => Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light)),
  /** A selection tick: choosing a segment, a chip, a tab, the theme. */
  select: () => run(() => Haptics.selectionAsync()),
  /** Something worked: a booking made, a change saved. */
  success: () => run(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success)),
  warning: () => run(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning)),
  /** Something failed. */
  error: () => run(() => Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error)),
};
