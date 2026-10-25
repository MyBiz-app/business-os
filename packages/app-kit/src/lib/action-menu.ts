import { ActionSheetIOS, Alert, Platform } from "react-native";

import { haptics } from "./haptics";

export type MenuAction = { label: string; onPress: () => void; destructive?: boolean };

/**
 * The menu a long press opens: the system action sheet on iOS, an alert with buttons on Android.
 * The web has no long press, so it does nothing there; every action is also a visible button.
 */
export function showActionMenu(title: string, actions: MenuAction[], closeLabel: string) {
  if (Platform.OS === "web" || actions.length === 0) return;
  haptics.tap();
  if (Platform.OS === "ios") {
    ActionSheetIOS.showActionSheetWithOptions(
      {
        title,
        options: [...actions.map((a) => a.label), closeLabel],
        cancelButtonIndex: actions.length,
        destructiveButtonIndex: actions.findIndex((a) => a.destructive) >= 0 ? actions.findIndex((a) => a.destructive) : undefined,
      },
      (index) => actions[index]?.onPress(),
    );
    return;
  }
  Alert.alert(title, undefined, [
    ...actions.map((a) => ({ text: a.label, style: a.destructive ? ("destructive" as const) : ("default" as const), onPress: a.onPress })),
    { text: closeLabel, style: "cancel" as const },
  ]);
}
