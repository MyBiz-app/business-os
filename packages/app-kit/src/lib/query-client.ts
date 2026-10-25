import AsyncStorage from "@react-native-async-storage/async-storage";
import { createAsyncStoragePersister } from "@tanstack/query-async-storage-persister";
import { QueryClient } from "@tanstack/react-query";

/** How long a screen's data counts as fresh: switching tabs inside this window asks the server nothing. */
export const FRESH_MS = 20_000;
/** How long saved data is kept on the device and shown first on the next open. */
export const KEEP_MS = 24 * 60 * 60 * 1000;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: FRESH_MS, gcTime: KEEP_MS, retry: 1, refetchOnWindowFocus: false },
  },
});

export const queryPersister = createAsyncStoragePersister({
  storage: AsyncStorage,
  key: "bos.query-cache",
  throttleTime: 2000,
});

/** Forget everything saved: on sign-out, or when another person signs in on this device. */
export async function clearQueryCache(): Promise<void> {
  queryClient.clear();
  await queryPersister.removeClient();
}
