import AsyncStorage from "@react-native-async-storage/async-storage";
import { createClient } from "@supabase/supabase-js";
import * as SecureStore from "expo-secure-store";
import { AppState, Platform } from "react-native";

import { createChunkedStorage } from "./chunked-storage";
import { SUPABASE_KEY, SUPABASE_URL } from "./env";

// SecureStore keys may only contain letters, digits, ".", "-" and "_".
const secureKey = (key: string) => key.replace(/[^\w.-]/g, "_");

// Sign-in tokens live in the phone's Keychain / Keystore. The web has no secure store, so there
// the browser's own storage stays in use.
const storage =
  Platform.OS === "web"
    ? AsyncStorage
    : createChunkedStorage(
        {
          getItem: (key) => SecureStore.getItemAsync(secureKey(key)),
          setItem: (key, value) => SecureStore.setItemAsync(secureKey(key), value),
          removeItem: (key) => SecureStore.deleteItemAsync(secureKey(key)),
        },
        AsyncStorage,
      );

export const supabase = createClient(SUPABASE_URL, SUPABASE_KEY, {
  auth: {
    storage,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});

// Refresh tokens only while the app is in the foreground.
if (Platform.OS !== "web") {
  AppState.addEventListener("change", (state) => {
    if (state === "active") void supabase.auth.startAutoRefresh();
    else void supabase.auth.stopAutoRefresh();
  });
}
