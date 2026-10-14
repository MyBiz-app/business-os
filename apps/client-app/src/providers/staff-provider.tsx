import type { ApiClient, components } from "@business-os/api-client";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { ApiError, apiClient, unwrap } from "@business-os/app-kit/lib/api";
import { brandPalette } from "@business-os/app-kit/lib/brand";
import type { Palette } from "@business-os/app-kit/lib/theme";
import { useAreas } from "@/providers/area-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

export type Tenant = components["schemas"]["Tenant"];
export type Branch = { id: string; name: string };
/** A business the person belongs to that was closed (it is locked until its owner reopens it). */
export type ClosedBusiness = { id: string; name: string; owner: boolean };

/** The current branch, remembered per business (none: all branches). */
const branchKey = (tenantId: string) => `business.branch.${tenantId}`;

type StaffContextValue = {
  /** The business being worked in, with this person's permissions in it. */
  tenant: Tenant | null;
  /** Set instead of `tenant` while the chosen business is closed. */
  closedBusiness: ClosedBusiness | null;
  api: ApiClient;
  /** Scopes requests to the business and, when one is chosen, to the current branch. */
  scope: { header: { "X-Tenant-Id": string; "X-Location-Id"?: string } };
  /** The business's active branches (empty when the person may not read them). */
  branches: Branch[];
  branch: Branch | null;
  selectBranch: (branchId: string | null) => Promise<void>;
  palette: Palette;
  can: (permission: string) => boolean;
  refresh: () => Promise<void>;
};

const StaffContext = createContext<StaffContextValue | null>(null);

/** The business this person works in: the one their active business area points at, with their
 * permissions in it. The API checks every permission again on each request. */
export function StaffProvider({ children }: { children: React.ReactNode }) {
  const { active } = useAreas();
  const { palette } = useTheme();
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [closedBusiness, setClosedBusiness] = useState<ClosedBusiness | null>(null);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [branchId, setBranchId] = useState<string | null>(null);
  // Only a business area loads a business; in any other area nothing is fetched.
  const tenantId = active?.kind === "business" ? (active.tenantId ?? null) : null;
  const ownerRole = active?.role === "owner";
  const tenantName = active?.name ?? "";

  const load = useCallback(async (id: string | null) => {
    setClosedBusiness(null);
    if (!id) {
      setTenant(null);
      setBranches([]);
      setBranchId(null);
      return;
    }
    const header = { "X-Tenant-Id": id };
    let current: Tenant;
    try {
      current = unwrap(await apiClient().GET("/tenants/current", { params: { header } }));
    } catch (error) {
      if (!(error instanceof ApiError) || error.detail !== "business_closed") throw error;
      setTenant(null);
      setBranches([]);
      setBranchId(null);
      setClosedBusiness({ id, name: tenantName, owner: ownerRole });
      return;
    }
    const list = current.permissions.includes("catalog.read")
      ? ((await apiClient().GET("/locations", { params: { header } })).data ?? []).filter((b) => b.active)
      : [];
    const stored = await AsyncStorage.getItem(branchKey(id));
    setBranches(list.map(({ id: branch, name }) => ({ id: branch, name })));
    setBranchId(list.length > 1 && list.some((b) => b.id === stored) ? stored : null);
    setTenant(current);
  }, [tenantName, ownerRole]);

  const refresh = useCallback(() => load(tenantId), [load, tenantId]);

  useEffect(() => {
    setTenant(null);
    setClosedBusiness(null);
    void load(tenantId).catch(() => undefined);
    // Reload only when the area changes, not when its display name does.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantId]);

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
      tenant,
      closedBusiness,
      api: apiClient(),
      scope: { header: { "X-Tenant-Id": tenant?.id ?? "", ...(branchId ? { "X-Location-Id": branchId } : {}) } },
      branches,
      branch: branches.find((b) => b.id === branchId) ?? null,
      selectBranch,
      palette: brandPalette(palette, tenant?.primary_color),
      can: (permission: string) => tenant?.permissions.includes(permission) ?? false,
      refresh,
    }),
    [tenant, closedBusiness, palette, refresh, branches, branchId, selectBranch],
  );

  return <StaffContext.Provider value={value}>{children}</StaffContext.Provider>;
}

export function useStaff(): StaffContextValue {
  const context = useContext(StaffContext);
  if (!context) throw new Error("useStaff must be used inside StaffProvider");
  return context;
}
