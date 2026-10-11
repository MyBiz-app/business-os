import type { ApiClient, components } from "@business-os/api-client";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { apiClient, unwrap } from "@business-os/app-kit/lib/api";
import { brandPalette } from "@business-os/app-kit/lib/brand";
import type { Palette } from "@business-os/app-kit/lib/theme";
import { useSession } from "@business-os/app-kit/providers/session-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

export type ClientBusiness = components["schemas"]["ClientBusiness"];

const SELECTED_KEY = "client.business";

type BusinessContextValue = {
  /** null until loaded (or while signed out). */
  businesses: ClientBusiness[] | null;
  business: ClientBusiness | null;
  api: ApiClient;
  /** Request parameters that select the business: `params: { ...scope, ... }`. */
  scope: { header: { "X-Tenant-Id": string } };
  palette: Palette;
  select: (tenantId: string) => Promise<void>;
  join: (code: string) => Promise<ClientBusiness>;
  refresh: () => Promise<void>;
};

const BusinessContext = createContext<BusinessContextValue | null>(null);

export function BusinessProvider({ children }: { children: React.ReactNode }) {
  const { session } = useSession();
  const { palette } = useTheme();
  const [businesses, setBusinesses] = useState<ClientBusiness[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const userId = session?.user.id;

  const refresh = useCallback(async () => {
    if (!userId) {
      setBusinesses(null);
      return;
    }
    const [list, stored] = await Promise.all([
      apiClient().GET("/client/businesses").then(unwrap),
      AsyncStorage.getItem(SELECTED_KEY),
    ]);
    setBusinesses(list);
    setSelectedId(list.some((b) => b.id === stored) ? stored : (list[0]?.id ?? null));
  }, [userId]);

  useEffect(() => {
    void refresh().catch(() => setBusinesses([]));
  }, [refresh]);

  const select = useCallback(async (tenantId: string) => {
    setSelectedId(tenantId);
    await AsyncStorage.setItem(SELECTED_KEY, tenantId);
  }, []);

  const join = useCallback(
    async (code: string) => {
      const joined = unwrap(await apiClient().POST("/client/businesses", { body: { code } }));
      setBusinesses((current) => [...(current ?? []).filter((b) => b.id !== joined.id), joined]);
      await select(joined.id);
      return joined;
    },
    [select],
  );

  const business = businesses?.find((b) => b.id === selectedId) ?? null;
  const value = useMemo(
    () => ({
      businesses,
      business,
      api: apiClient(),
      scope: { header: { "X-Tenant-Id": business?.id ?? "" } },
      palette: brandPalette(palette, business?.primary_color),
      select,
      join,
      refresh,
    }),
    [businesses, business, palette, select, join, refresh],
  );

  return <BusinessContext.Provider value={value}>{children}</BusinessContext.Provider>;
}

export function useBusiness(): BusinessContextValue {
  const context = useContext(BusinessContext);
  if (!context) throw new Error("useBusiness must be used inside BusinessProvider");
  return context;
}
