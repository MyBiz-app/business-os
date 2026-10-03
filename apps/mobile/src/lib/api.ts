import Constants from "expo-constants";

// On a phone, "localhost" is the phone itself. In development we reach the API on the
// computer that runs the Expo dev server (same Wi-Fi), using the host Expo reports.
function resolveApiUrl(): string {
  const configured = process.env.EXPO_PUBLIC_API_URL;
  if (configured) return configured;
  const devHost = Constants.expoConfig?.hostUri?.split(":")[0];
  return `http://${devHost ?? "localhost"}:8000`;
}

export const API_URL = resolveApiUrl();

export async function isApiHealthy(): Promise<boolean> {
  try {
    const response = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(3000) });
    return response.ok;
  } catch {
    return false;
  }
}
