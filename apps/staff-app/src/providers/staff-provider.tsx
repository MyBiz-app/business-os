import type { ApiClient, components } from "@business-os/api-client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { apiClient, unwrap } from "@business-os/app-kit/lib/api";
import { useSession } from "@business-os/app-kit/providers/session-provider";

export type StaffMe = components["schemas"]["StaffMe"];
export type PlatformPermission = StaffMe["permissions"][number];

type StaffContextValue = {
  /** null while loading or signed out; undefined-level means not on the team. */
  staff: StaffMe | null;
  onTeam: boolean | null;
  api: ApiClient;
  can: (permission: PlatformPermission) => boolean;
  refresh: () => Promise<void>;
};

const StaffContext = createContext<StaffContextValue | null>(null);

/** Who the signed-in person is on the MyBiz team, and what they may do. */
export function StaffProvider({ children }: { children: React.ReactNode }) {
  const { session } = useSession();
  const [staff, setStaff] = useState<StaffMe | null>(null);
  const [onTeam, setOnTeam] = useState<boolean | null>(null);
  const userId = session?.user.id;

  const refresh = useCallback(async () => {
    if (!userId) {
      setStaff(null);
      setOnTeam(null);
      return;
    }
    try {
      setStaff(unwrap(await apiClient().GET("/platform/me")));
      setOnTeam(true);
    } catch {
      setStaff(null);
      setOnTeam(false);
    }
  }, [userId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo(
    () => ({
      staff,
      onTeam,
      api: apiClient(),
      can: (permission: PlatformPermission) => staff?.permissions.includes(permission) ?? false,
      refresh,
    }),
    [staff, onTeam, refresh],
  );

  return <StaffContext.Provider value={value}>{children}</StaffContext.Provider>;
}

export function useStaff(): StaffContextValue {
  const context = useContext(StaffContext);
  if (!context) throw new Error("useStaff must be used inside StaffProvider");
  return context;
}
