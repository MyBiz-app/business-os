import { Alert, Platform } from "react-native";

import { haptics } from "./haptics";

/** A native yes/no dialog (window.confirm on the web, where Alert has no buttons). */
export function confirm(title: string, message: string, yes: string, no: string): Promise<boolean> {
  haptics.warning();
  if (Platform.OS === "web") return Promise.resolve(window.confirm(`${title}\n\n${message}`));
  return new Promise((resolve) =>
    Alert.alert(title, message, [
      { text: no, style: "cancel", onPress: () => resolve(false) },
      { text: yes, style: "destructive", onPress: () => resolve(true) },
    ]),
  );
}
