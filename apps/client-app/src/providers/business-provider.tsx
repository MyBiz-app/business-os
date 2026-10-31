import type { ApiClient, components } from "@business-os/api-client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { legalVersion } from "@business-os/i18n/brand";
import { apiClient, unwrap } from "@business-os/app-kit/lib/api";
import { brandPalette } from "@business-os/app-kit/lib/brand";
import { remembered } from "@business-os/app-kit/lib/remembered";
import type { Palette } from "@business-os/app-kit/lib/theme";
import { useSession } from "@business-os/app-kit/providers/session-provider";
import { useTheme } from "@business-os/app-kit/providers/theme-provider";

export type ClientBusiness = components["schemas"]["ClientBusiness"];

const SELECTED_KEY = "client.business";
/** Waits before each automatic new try after a failed load (a sleeping server needs a moment). */
const RETRY_AFTER_MS = [2000, 5000, 12000];

type BusinessContextValue = {
  /** null until loaded (or while signed out, or when loading failed: see `failed`). An empty list
   * always means "this person has no business", never "it could not be loaded". */
  businesses: ClientBusiness[] | null;
  /** The list could not be loaded (the server was unreachable); it is tried again by itself. */
  failed: boolean;
  /** What went wrong, as the technical message (shown small under the retry, for support). */
  failure: string | null;
  /** Tries to load the list again, now. */
  retry: () => void;
  business: ClientBusiness | null;
  api: ApiClient;
  /** Request parameters that select the business: `params: { ...scope, ... }`. */
  scope: { header: { "X-Tenant-Id": string } };
  palette: Palette;
  select: (tenantId: string) => Promise<void>;
  join: (code: string) => Promise<ClientBusiness>;
  /** A team member signs up as a client of their own business, without a code. */
  joinOwn: (tenantId: string) => Promise<ClientBusiness>;
  refresh: () => Promise<void>;
};

const BusinessContext = createContext<BusinessContextValue | null>(null);

export function BusinessProvider({ children }: { children: React.ReactNode }) {
  const { session } = useSession();
  const { palette } = useTheme();
  const [businesses, setBusinesses] = useState<ClientBusiness[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [tries, setTries] = useState(0);
  const userId = session?.user.id;

  const refresh = useCallback(async () => {
    if (!userId) {
      setBusinesses(null);
      return;
    }
    const [list, stored] = await Promise.all([
      apiClient().GET("/client/businesses").then(unwrap),
      remembered.read(SELECTED_KEY),
    ]);
    setBusinesses(list);
    setSelectedId(list.some((b) => b.id === stored) ? stored : (list[0]?.id ?? null));
  }, [userId]);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    const load = () => {
      refresh().then(
        () => {
          if (cancelled) return;
          setFailed(false);
          setFailure(null);
        },
        (error: unknown) => {
          if (cancelled) return;
          // Never turn "could not load" into "no businesses": that sends a member to the join screen.
          setFailed(true);
          setFailure(error instanceof Error ? error.message : String(error));
          if (attempt < RETRY_AFTER_MS.length) timer = setTimeout(load, RETRY_AFTER_MS[attempt++]);
        },
      );
    };
    load();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [refresh, tries]);
  const retry = useCallback(() => setTries((n) => n + 1), []);

  const select = useCallback(async (tenantId: string) => {
    setSelectedId(tenantId);
    await remembered.write(SELECTED_KEY, tenantId);
  }, []);

  const join = useCallback(
    async (code: string) => {
      const joined = unwrap(await apiClient().POST("/client/businesses", {
          body: { code, accepted_legal: { terms: legalVersion("terms"), privacy: legalVersion("privacy") } },
        }));
      setBusinesses((current) => [...(current ?? []).filter((b) => b.id !== joined.id), joined]);
      await select(joined.id);
      return joined;
    },
    [select],
  );

  const joinOwn = useCallback(async (tenantId: string) => {
    const joined = unwrap(await apiClient().POST("/client/businesses/self", { body: { tenant_id: tenantId } }));
    setBusinesses((current) => [...(current ?? []).filter((b) => b.id !== joined.id), joined]);
    await select(joined.id);
    return joined;
  }, [select]);

  const business = businesses?.find((b) => b.id === selectedId) ?? null;
  const value = useMemo(
    () => ({
      businesses,
      failed,
      failure,
      retry,
      business,
      api: apiClient(),
      scope: { header: { "X-Tenant-Id": business?.id ?? "" } },
      palette: brandPalette(palette, business?.primary_color),
      select,
      join,
      joinOwn,
      refresh,
    }),
    [businesses, failed, failure, retry, business, palette, select, join, joinOwn, refresh],
  );

  return <BusinessContext.Provider value={value}>{children}</BusinessContext.Provider>;
}

export function useBusiness(): BusinessContextValue {
  const context = useContext(BusinessContext);
  if (!context) throw new Error("useBusiness must be used inside BusinessProvider");
  return context;
}
