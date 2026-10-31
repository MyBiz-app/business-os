import AsyncStorage from "@react-native-async-storage/async-storage";
import { router } from "expo-router";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { BRAND } from "@business-os/i18n/brand";
import { fetchMe } from "@business-os/app-kit/lib/me";
import { areaHome, buildAreas, pickArea, type Area, type AreaKind } from "@business-os/app-kit/lib/areas";
import { useSession } from "@business-os/app-kit/providers/session-provider";
import { useBusiness } from "@/providers/business-provider";

const ACTIVE_KEY = "app.area";

/** Areas whose screens live in this app. */
export const READY_AREAS: readonly AreaKind[] = ["client", "business", "platform"];

type AreaContextValue = {
  /** null until loaded (or while signed out, or while loading failed: see `failed`). */
  areas: Area[] | null;
  /** The person's businesses or roles could not be loaded; shown with a retry, never as "no business". */
  failed: boolean;
  retry: () => void;
  active: Area | null;
  /** Opens an area and remembers it as the last one used. */
  switchTo: (key: string) => Promise<void>;
};

const AreaContext = createContext<AreaContextValue | null>(null);

/** Everything the signed-in person can be in this app: the MyBiz team, businesses they work in,
 * businesses they are a client of. Opens the last one used and lets them switch. */
export function AreaProvider({ children }: { children: React.ReactNode }) {
  const { session } = useSession();
  const { businesses, failed: businessesFailed, retry: retryBusinesses, select, joinOwn } = useBusiness();
  const userId = session?.user.id;
  const [identity, setIdentity] = useState<{ platformAdmin: boolean; memberships: Parameters<typeof buildAreas>[0]["memberships"] } | null>(null);
  const [storedKey, setStoredKey] = useState<string | null>(null);
  // /me could not be read: the person still gets their client areas, but with no business at all
  // that is a failure to load, not an empty account.
  const [identityFailed, setIdentityFailed] = useState(false);
  const [tries, setTries] = useState(0);

  useEffect(() => {
    if (!userId) {
      setIdentity(null);
      return;
    }
    let cancelled = false;
    void Promise.all([fetchMe(), AsyncStorage.getItem(ACTIVE_KEY)])
      .then(([me, stored]) => {
        if (cancelled) return;
        setIdentity({ platformAdmin: me.platform_admin, memberships: me.memberships });
        setStoredKey(stored);
        setIdentityFailed(false);
      })
      // Not being able to read /me must never lock a client out of their own area.
      .catch(() => {
        if (cancelled) return;
        setIdentity({ platformAdmin: false, memberships: [] });
        setIdentityFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [userId, tries]);

  const noBusinessLoaded = identityFailed && (businesses?.length ?? 0) === 0;
  const failed = businessesFailed || noBusinessLoaded;
  const retry = useCallback(() => {
    setTries((n) => n + 1);
    retryBusinesses();
  }, [retryBusinesses]);

  // Tried again by itself a few times, so a server that was asleep does not need a tap.
  useEffect(() => {
    if (!noBusinessLoaded || tries >= 3) return;
    const timer = setTimeout(() => setTries((n) => n + 1), 2000 * (tries + 1));
    return () => clearTimeout(timer);
  }, [noBusinessLoaded, tries]);

  const areas = useMemo(
    () => (identity && businesses && !noBusinessLoaded ? buildAreas({ ...identity, businesses, platformName: BRAND.name }) : null),
    [identity, businesses, noBusinessLoaded],
  );
  const active = useMemo(() => (areas ? pickArea(areas, storedKey, READY_AREAS) : null), [areas, storedKey]);

  const switchTo = useCallback(
    async (key: string) => {
      const next = areas?.find((a) => a.key === key);
      if (!next) return;
      // A team member's first visit to their business as a client makes their client card.
      if (next.joinOnOpen && next.tenantId) await joinOwn(next.tenantId);
      setStoredKey(key);
      await AsyncStorage.setItem(ACTIVE_KEY, key);
      if (next.kind === "client" && next.tenantId) await select(next.tenantId);
      router.replace(areaHome(next));
    },
    [areas, select, joinOwn],
  );

  const value = useMemo(() => ({ areas, failed, retry, active, switchTo }), [areas, failed, retry, active, switchTo]);
  return <AreaContext.Provider value={value}>{children}</AreaContext.Provider>;
}

export function useAreas(): AreaContextValue {
  const context = useContext(AreaContext);
  if (!context) throw new Error("useAreas must be used inside AreaProvider");
  return context;
}
