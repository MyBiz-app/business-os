"use server";

import { getLocale, getTranslations } from "next-intl/server";

import { MIN_SEARCH_LENGTH, type PaletteHit, toPaletteHit } from "@/lib/command-palette";
import { dayOf, formatDay, formatTime } from "@/lib/dates";
import { getTenant } from "@/lib/tenant";

/** What the Cmd+K window finds for a typed text, in the open business and branch. The API decides
 * what the person may see (permissions, branches); null when the search can't be reached. */
export async function searchEverything(query: string): Promise<PaletteHit[] | null> {
  const q = query.trim().slice(0, 100);
  if (q.length < MIN_SEARCH_LENGTH) return [];
  const { api, scope, tenant } = await getTenant();
  try {
    const { data } = await api.GET("/search", { params: { ...scope, query: { q } } });
    if (!data) return null;
    const [t, locale] = await Promise.all([getTranslations(), getLocale()]);
    const zone = tenant.time_zone;
    const labels = {
      stage: Object.fromEntries(["new", "contacted", "trial", "offer", "won", "lost"].map((key) => [key, t(`leads.stages.${key}` as "leads.stages.new")])),
      role: Object.fromEntries(["owner", "manager", "branch_manager", "staff", "front_desk"].map((key) => [key, t(`roles.${key}` as "roles.owner")])),
      document: Object.fromEntries(
        ["tax_invoice_receipt", "tax_invoice", "credit_note", "quote", "transaction_invoice"].map((key) => [key, t(`invoices.kinds.${key}` as "invoices.kinds.quote")]),
      ),
      when: (instant: string) => `${formatDay(dayOf(instant, zone), locale, { day: "numeric", month: "short" })} ${formatTime(instant, locale, zone)}`,
    };
    return data.items.map((item) => toPaletteHit(item, labels));
  } catch {
    return null;
  }
}
