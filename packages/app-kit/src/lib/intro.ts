import AsyncStorage from "@react-native-async-storage/async-storage";

const KEY = "intro.seen";

/** Whether this phone has already shown the first-run intro. A storage problem counts as seen: never trap someone in it. */
export async function introSeen(): Promise<boolean> {
  try {
    return (await AsyncStorage.getItem(KEY)) !== null;
  } catch {
    return true;
  }
}

export async function markIntroSeen(): Promise<void> {
  try {
    await AsyncStorage.setItem(KEY, "1");
  } catch {
    // the intro may show once more; nothing is lost
  }
}
