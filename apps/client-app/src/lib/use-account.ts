import type { components } from "@business-os/api-client";
import { useFocusEffect } from "expo-router";

import { useCachedLoad } from "@business-os/app-kit/lib/use-cached-load";
import { dataKey, fetchDocuments, fetchQuotes, fetchReceipts, fetchServices } from "@/lib/client-data";
import { useDataContext } from "@/lib/use-data-context";

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
 * is waiting for them; the last copy shows at once and is refreshed whenever the screen comes back
 * into focus. A part that fails to load is left empty, so the screen still shows the rest. */
export function useAccount(): Account {
  const ctx = useDataContext();
  const { data, revalidate } = useCachedLoad(
    ctx ? dataKey(ctx, "account") : ["account"],
    async (): Promise<Account> => {
      if (!ctx) return EMPTY;
      const list = <T,>(request: Promise<T[]>) => request.catch(() => [] as T[]);
      const [quotes, documents, services, receipts] = await Promise.all([
        list(fetchQuotes(ctx)),
        list(fetchDocuments(ctx)),
        list(fetchServices(ctx)),
        list(fetchReceipts(ctx)),
      ]);
      return {
        quotes,
        documents,
        toPay: quotes.filter((q) => q.deposit_due > 0),
        toAnswer: quotes.filter((q) => q.status === "sent"),
        toSign: documents.filter((d) => d.sign_requested && !d.signed_at),
        receipts: receipts.length,
        onSite: services.some((s) => s.on_site),
      };
    },
    { enabled: Boolean(ctx) },
  );
  useFocusEffect(revalidate);
  return ctx ? (data ?? EMPTY) : EMPTY;
}
