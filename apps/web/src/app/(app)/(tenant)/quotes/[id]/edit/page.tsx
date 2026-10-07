import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { toMajorUnits } from "@/lib/money";
import { getTenantFor } from "@/lib/tenant";

import { updateQuote } from "../../actions";
import { QuoteForm } from "../../quote-form";

/** Editing a draft (a sent quote is changed by copying it). */
export default async function EditQuotePage({ params }: PageProps<"/quotes/[id]/edit">) {
  const { id } = await params;
  const t = await getTranslations("quotes");
  const { tenant, api, scope } = await getTenantFor("sales.manage");
  const { data: quote } = await api.GET("/quotes/{quote_id}", { params: { ...scope, path: { quote_id: id } } });
  if (!quote) notFound();
  if (quote.status !== "draft") redirect(`/quotes/${id}`);
  const local = quote.event_starts_at
    ? new Intl.DateTimeFormat("sv-SE", { dateStyle: "short", timeStyle: "short", timeZone: tenant.time_zone }).format(new Date(quote.event_starts_at)).split(" ")
    : ["", ""];

  return (
    <main className="enter mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 py-8 sm:px-6">
      <Link href={`/quotes/${id}`} className="text-sm text-primary underline-offset-4 hover:underline">{t("back")}</Link>
      <h1 className="text-3xl font-bold">
        <span className="tabular-nums text-muted">#{quote.number}</span> {t("edit")}
      </h1>
      <section className="card p-6">
        <QuoteForm
          action={updateQuote.bind(null, id)}
          currency={tenant.currency}
          submitLabel={t("saveDraft")}
          defaults={{
            title: quote.title,
            lines: quote.lines.map((l) => ({ description: l.description, quantity: String(Number(l.quantity)), price: toMajorUnits(l.unit_price, quote.currency) })),
            deposit_percent: quote.deposit_percent,
            valid_until: quote.valid_until ?? "",
            event_date: local[0] ?? "",
            event_time: local[1] ?? "",
            event_place: quote.event_place ?? "",
            notes: quote.notes ?? "",
          }}
        />
      </section>
    </main>
  );
}
