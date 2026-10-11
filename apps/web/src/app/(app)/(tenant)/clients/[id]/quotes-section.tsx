import { FileSignature, Plus } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import type { getTenant } from "@/lib/tenant";

import { STATUS_TONE } from "../../quotes/status";

type Context = Awaited<ReturnType<typeof getTenant>>;

/** The client's quotes (#44), newest first, and a new one for them. */
export async function QuotesSection({ clientId, context, locked }: { clientId: string; context: Context; locked: boolean }) {
  const { api, scope, tenant } = context;
  const quotes = unwrap(await api.GET("/quotes", { params: { ...scope, query: { client_id: clientId } } }));
  const canSell = !locked && tenant.permissions.includes("sales.manage");
  if (quotes.length === 0 && !canSell) return null;
  const t = await getTranslations("quotes");
  const locale = await getLocale();

  return (
    <section aria-labelledby="quotes-heading" className="flex flex-col gap-3 card p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="quotes-heading" className="flex items-center gap-2 text-lg font-semibold">
          <FileSignature aria-hidden="true" className="size-5 text-primary" />
          {t("title")}
        </h2>
        {canSell && (
          <Link href={`/quotes/new?client=${clientId}`} className="btn-secondary px-3 py-1.5 text-sm">
            <Plus aria-hidden="true" className="size-4" /> {t("new")}
          </Link>
        )}
      </div>
      {quotes.length === 0 ? (
        <p className="text-sm text-muted">{t("noneForClient")}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-border">
          {quotes.map((quote) => (
            <li key={quote.id}>
              <Link href={`/quotes/${quote.id}`} className="flex flex-wrap items-center justify-between gap-2 py-2.5 underline-offset-4 hover:underline">
                <span dir="auto">#{quote.number} · {quote.title}</span>
                <span className="flex items-center gap-2 text-sm">
                  <span className="tabular-nums">{formatMoney(quote.total, quote.currency, locale)}</span>
                  <Pill tone={STATUS_TONE[quote.status]}>{t(`statuses.${quote.status}`)}</Pill>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
