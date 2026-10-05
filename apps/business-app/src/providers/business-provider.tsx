import type { ApiClient, components } from "@business-os/api-client";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { apiClient, unwrap } from "@business-os/app-kit/lib/api";
import { brandPalette } from "@business-os/app-kit/lib/brand";
import type { Palette } from "@business-os/app-kit/lib/theme";
import { useSession } from "@business-os/app-kit/providers/session-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

export type Tenant = components["schemas"]["Tenant"];
export type Membership = components["schemas"]["Membership"];
export type Branch = { id: string; name: string };

const SELECTED_KEY = "business.tenant";
/** The current branch, remembered per business (none: all branches). */
const branchKey = (tenantId: string) => `business.branch.${tenantId}`;

type BusinessContextValue = {
  /** null while loading or signed out; [] when this person runs no business. */
  memberships: Membership[] | null;
  /** The business being worked in, with this person's permissions in it. */
  tenant: Tenant | null;
  api: ApiClient;
  /** Scopes requests to the business and, when one is chosen, to the current branch. */
  scope: { header: { "X-Tenant-Id": string; "X-Location-Id"?: string } };
  /** The business's active branches (empty when the person may not read them). */
  branches: Branch[];
  branch: Branch | null;
  selectBranch: (branchId: string | null) => Promise<void>;
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
  const [branches, setBranches] = useState<Branch[]>([]);
  const [branchId, setBranchId] = useState<string | null>(null);
  const userId = session?.user.id;

  const load = useCallback(async (tenantId: string | null) => {
    if (!tenantId) {
      setTenant(null);
      setBranches([]);
      setBranchId(null);
      return;
    }
    const header = { "X-Tenant-Id": tenantId };
    const current = unwrap(await apiClient().GET("/tenants/current", { params: { header } }));
    const active = current.permissions.includes("catalog.read")
      ? ((await apiClient().GET("/locations", { params: { header } })).data ?? []).filter((b) => b.active)
      : [];
    const stored = await AsyncStorage.getItem(branchKey(tenantId));
    setBranches(active.map(({ id, name }) => ({ id, name })));
    setBranchId(active.length > 1 && active.some((b) => b.id === stored) ? stored : null);
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

  const selectBranch = useCallback(
    async (next: string | null) => {
      if (!tenant) return;
      if (next) await AsyncStorage.setItem(branchKey(tenant.id), next);
      else await AsyncStorage.removeItem(branchKey(tenant.id));
      setBranchId(next);
    },
    [tenant],
  );

  const value = useMemo(
    () => ({
      memberships,
      tenant,
      api: apiClient(),
      scope: { header: { "X-Tenant-Id": tenant?.id ?? "", ...(branchId ? { "X-Location-Id": branchId } : {}) } },
      branches,
      branch: branches.find((b) => b.id === branchId) ?? null,
      selectBranch,
      palette: brandPalette(palette, tenant?.primary_color),
      can: (permission: string) => tenant?.permissions.includes(permission) ?? false,
      select,
      refresh,
    }),
    [memberships, tenant, palette, select, refresh, branches, branchId, selectBranch],
  );

  return <BusinessContext.Provider value={value}>{children}</BusinessContext.Provider>;
}

export function useBusiness(): BusinessContextValue {
  const context = useContext(BusinessContext);
  if (!context) throw new Error("useBusiness must be used inside BusinessProvider");
  return context;
}
