import AsyncStorage from "@react-native-async-storage/async-storage";
import { router } from "expo-router";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { apiClient, unwrap } from "@business-os/app-kit/lib/api";
import { areaHome, buildAreas, pickArea, type Area, type AreaKind } from "@business-os/app-kit/lib/areas";
import { useSession } from "@business-os/app-kit/providers/session-provider";
import { useBusiness } from "@/providers/business-provider";

const ACTIVE_KEY = "app.area";

/** Areas whose screens already live in this app. R5 adds `business`, R6 adds `platform`. */
export const READY_AREAS: readonly AreaKind[] = ["client"];

type AreaContextValue = {
  /** null until loaded (or while signed out). */
  areas: Area[] | null;
  active: Area | null;
  /** Opens an area and remembers it as the last one used. */
  switchTo: (key: string) => Promise<void>;
};

const AreaContext = createContext<AreaContextValue | null>(null);

/** Everything the signed-in person can be in this app: the MyBiz team, businesses they work in,
 * businesses they are a client of. Opens the last one used and lets them switch. */
export function AreaProvider({ children }: { children: React.ReactNode }) {
  const { session } = useSession();
  const { businesses, select } = useBusiness();
  const userId = session?.user.id;
  const [identity, setIdentity] = useState<{ platformAdmin: boolean; memberships: Parameters<typeof buildAreas>[0]["memberships"] } | null>(null);
  const [storedKey, setStoredKey] = useState<string | null>(null);

  useEffect(() => {
    if (!userId) {
      setIdentity(null);
      return;
    }
    let cancelled = false;
    void Promise.all([apiClient().GET("/me").then(unwrap), AsyncStorage.getItem(ACTIVE_KEY)])
      .then(([me, stored]) => {
        if (cancelled) return;
        setIdentity({ platformAdmin: me.platform_admin, memberships: me.memberships });
        setStoredKey(stored);
      })
      // Not being able to read /me must never lock a client out of their own area.
      .catch(() => !cancelled && setIdentity({ platformAdmin: false, memberships: [] }));
    return () => {
      cancelled = true;
    };
  }, [userId]);

  const areas = useMemo(
    () => (identity && businesses ? buildAreas({ ...identity, businesses }) : null),
    [identity, businesses],
  );
  const active = useMemo(() => (areas ? pickArea(areas, storedKey, READY_AREAS) : null), [areas, storedKey]);

  const switchTo = useCallback(
    async (key: string) => {
      const next = areas?.find((a) => a.key === key);
      if (!next) return;
      setStoredKey(key);
      await AsyncStorage.setItem(ACTIVE_KEY, key);
      if (next.kind === "client" && next.tenantId) await select(next.tenantId);
      router.replace(areaHome(next));
    },
    [areas, select],
  );

  const value = useMemo(() => ({ areas, active, switchTo }), [areas, active, switchTo]);
  return <AreaContext.Provider value={value}>{children}</AreaContext.Provider>;
}

export function useAreas(): AreaContextValue {
  const context = useContext(AreaContext);
  if (!context) throw new Error("useAreas must be used inside AreaProvider");
  return context;
}
