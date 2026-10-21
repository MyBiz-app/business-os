import * as ExpoLocation from "expo-location";
import { useCallback, useState } from "react";

import type { GeoPoint } from "@business-os/app-kit/lib/distance";

export type PositionState = "idle" | "asking" | "ready" | "denied" | "unavailable";

/** The person's position, asked for only when they tap "near me". It stays on this device: it is
 * used to sort the branches and is never sent to the API or to any outside service. */
export function useDevicePosition() {
  const [state, setState] = useState<PositionState>("idle");
  const [position, setPosition] = useState<GeoPoint | null>(null);

  const request = useCallback(async () => {
    setState("asking");
    try {
      const { granted } = await ExpoLocation.requestForegroundPermissionsAsync();
      if (!granted) return setState("denied");
      const found = await ExpoLocation.getCurrentPositionAsync({ accuracy: ExpoLocation.Accuracy.Balanced });
      setPosition({ latitude: found.coords.latitude, longitude: found.coords.longitude });
      setState("ready");
    } catch {
      setState("unavailable");
    }
  }, []);

  return { state, position, request };
}
