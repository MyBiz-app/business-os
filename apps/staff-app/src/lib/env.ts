import Constants from "expo-constants";

// On a phone, "localhost" is the phone itself. In development we reach the API and the local
// Supabase on the computer that runs the Expo dev server (same Wi-Fi), using the host Expo
// reports. Other environments set EXPO_PUBLIC_* variables (see apps/mobile/README.md).
const devHost = Constants.expoConfig?.hostUri?.split(":")[0] ?? "localhost";

export const API_URL = process.env.EXPO_PUBLIC_API_URL || `http://${devHost}:8000`;

export const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL || `http://${devHost}:54321`;

// The public, well-known anon key of every local `supabase start` (safe to commit).
const LOCAL_SUPABASE_KEY =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0";

export const SUPABASE_KEY = process.env.EXPO_PUBLIC_SUPABASE_KEY || LOCAL_SUPABASE_KEY;
