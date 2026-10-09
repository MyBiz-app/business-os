import type { components } from "@business-os/api-client";
import { useFocusEffect } from "expo-router";
import { useCallback, useState } from "react";

import { useBusiness } from "@/providers/business-provider";

export type ClientQuote = components["schemas"]["ClientQuote"];
export type ClientDocument = components["schemas"]["Document"];

export type Account = {
  quotes: ClientQuote[];
  documents: ClientDocument[];
  /** Quotes and bills with something to pay now. */
  toPay: ClientQuote[];
  /** Sent quotes waiting for the client's answer. */
  toAnswer: ClientQuote[];
  /** Shared documents that ask for the client's signature. */
  toSign: ClientDocument[];
  /** How many receipts the client has (payments made). */
  receipts: number;
  /** On-site services: the client keeps addresses. */
  onSite: boolean;
};

const EMPTY: Account = { quotes: [], documents: [], toPay: [], toAnswer: [], toSign: [], receipts: 0, onSite: false };

/** What the client has in their account beyond bookings (quotes, bills, documents) and what of it
 * is waiting for them; refreshed whenever the screen comes back into focus. A part that fails to
 * load is left empty, so the screen still shows the rest. */
export function useAccount(): Account {
  const { api, scope, business } = useBusiness();
  const [account, setAccount] = useState<Account>(EMPTY);

  useFocusEffect(
    useCallback(() => {
      if (!business) {
        setAccount(EMPTY);
        return;
      }
      let active = true;
      const list = <T,>(request: Promise<{ data?: T[] }>) => request.then((r) => r.data ?? []).catch(() => [] as T[]);
      void Promise.all([
        list(api.GET("/client/quotes", { params: scope })),
        list(api.GET("/client/documents", { params: scope })),
        list(api.GET("/client/appointments/services", { params: scope })),
        list(api.GET("/client/receipts", { params: scope })),
      ]).then(([quotes, documents, services, receipts]) => {
        if (!active) return;
        setAccount({
          quotes,
          documents,
          toPay: quotes.filter((q) => q.deposit_due > 0),
          toAnswer: quotes.filter((q) => q.status === "sent"),
          toSign: documents.filter((d) => d.sign_requested && !d.signed_at),
          receipts: receipts.length,
          onSite: services.some((s) => s.on_site),
        });
      });
      return () => {
        active = false;
      };
    }, [api, scope, business]),
  );
  return account;
}
