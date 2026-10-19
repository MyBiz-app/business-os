import type { ApiClient, components } from "@business-os/api-client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { ApiError, apiClient, unwrap } from "@business-os/app-kit/lib/api";
import { useSession } from "@business-os/app-kit/providers/session-provider";
import { useAreas } from "@/providers/area-provider";

export type StaffMe = components["schemas"]["StaffMe"];
export type PlatformPermission = StaffMe["permissions"][number];

type PlatformContextValue = {
  /** null while loading or signed out; undefined-level means not on the team. */
  staff: StaffMe | null;
  onTeam: boolean | null;
  /** On the team, but the API wants a two-step sign-in code first (not "off the team"). */
  mfaRequired: boolean;
  api: ApiClient;
  can: (permission: PlatformPermission) => boolean;
  refresh: () => Promise<void>;
};

const PlatformContext = createContext<PlatformContextValue | null>(null);

/** Who the signed-in person is on the MyBiz team, and what they may do. */
export function PlatformProvider({ children }: { children: React.ReactNode }) {
  const { session } = useSession();
  const [staff, setStaff] = useState<StaffMe | null>(null);
  const [onTeam, setOnTeam] = useState<boolean | null>(null);
  const [mfaRequired, setMfaRequired] = useState(false);
  const { active } = useAreas();
  const userId = session?.user.id;
  // Only people working in the MyBiz area ask the platform who they are.
  const inPlatform = active?.kind === "platform";

  const refresh = useCallback(async () => {
    if (!userId || !inPlatform) {
      setStaff(null);
      setOnTeam(null);
      setMfaRequired(false);
      return;
    }
    try {
      setStaff(unwrap(await apiClient().GET("/platform/me")));
      setOnTeam(true);
      setMfaRequired(false);
    } catch (error) {
      setStaff(null);
      setOnTeam(false);
      setMfaRequired(error instanceof ApiError && error.detail === "mfa_required");
    }
  }, [userId, inPlatform]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo(
    () => ({
      staff,
      onTeam,
      mfaRequired,
      api: apiClient(),
      can: (permission: PlatformPermission) => staff?.permissions.includes(permission) ?? false,
      refresh,
    }),
    [staff, onTeam, mfaRequired, refresh],
  );

  return <PlatformContext.Provider value={value}>{children}</PlatformContext.Provider>;
}

export function usePlatform(): PlatformContextValue {
  const context = useContext(PlatformContext);
  if (!context) throw new Error("usePlatform must be used inside PlatformProvider");
  return context;
}
