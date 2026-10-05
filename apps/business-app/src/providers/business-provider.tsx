import type { ApiClient, components } from "@business-os/api-client";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { apiClient, unwrap } from "@/lib/api";
import { brandPalette } from "@/lib/brand";
import type { Palette } from "@/lib/theme";
import { useSession } from "@/providers/session-provider";
import { useTheme } from "@/providers/theme-provider";

export type Tenant = components["schemas"]["Tenant"];
export type Membership = components["schemas"]["Membership"];

const SELECTED_KEY = "business.tenant";

type BusinessContextValue = {
  /** null while loading or signed out; [] when this person runs no business. */
  memberships: Membership[] | null;
  /** The business being worked in, with this person's permissions in it. */
  tenant: Tenant | null;
  api: ApiClient;
  scope: { header: { "X-Tenant-Id": string } };
  palette: Palette;
  can: (permission: string) => boolean;
  select: (tenantId: string) => Promise<void>;
  refresh: () => Promise<void>;
};

const BusinessContext = createContext<BusinessContextValue | null>(null);

/** The business this staff member is working in: their memberships, the chosen one and its
 * permissions. The API checks every permission again on each request. */
export function BusinessProvider({ children }: { children: React.ReactNode }) {
  const { session } = useSession();
  const { palette } = useTheme();
  const [memberships, setMemberships] = useState<Membership[] | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const userId = session?.user.id;

  const load = useCallback(async (tenantId: string | null) => {
    if (!tenantId) {
      setTenant(null);
      return;
    }
    const current = unwrap(
      await apiClient().GET("/tenants/current", { params: { header: { "X-Tenant-Id": tenantId } } }),
    );
    setTenant(current);
  }, []);

  const refresh = useCallback(async () => {
    if (!userId) {
      setMemberships(null);
      setTenant(null);
      return;
    }
    const [me, stored] = await Promise.all([
      apiClient().GET("/me").then(unwrap),
      AsyncStorage.getItem(SELECTED_KEY),
    ]);
    setMemberships(me.memberships);
    const chosen = me.memberships.some((m) => m.tenant_id === stored)
      ? stored
      : (me.memberships[0]?.tenant_id ?? null);
    await load(chosen);
  }, [userId, load]);

  useEffect(() => {
    void refresh().catch(() => setMemberships([]));
  }, [refresh]);

  const select = useCallback(
    async (tenantId: string) => {
      await AsyncStorage.setItem(SELECTED_KEY, tenantId);
      await load(tenantId);
    },
    [load],
  );

  const value = useMemo(
    () => ({
      memberships,
      tenant,
      api: apiClient(),
      scope: { header: { "X-Tenant-Id": tenant?.id ?? "" } },
      palette: brandPalette(palette, tenant?.primary_color),
      can: (permission: string) => tenant?.permissions.includes(permission) ?? false,
      select,
      refresh,
    }),
    [memberships, tenant, palette, select, refresh],
  );

  return <BusinessContext.Provider value={value}>{children}</BusinessContext.Provider>;
}

export function useBusiness(): BusinessContextValue {
  const context = useContext(BusinessContext);
  if (!context) throw new Error("useBusiness must be used inside BusinessProvider");
  return context;
}
