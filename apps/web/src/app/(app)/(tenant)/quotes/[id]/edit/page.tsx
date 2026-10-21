import { getTranslations } from "next-intl/server";
import { notFound, redirect } from "next/navigation";

import { toMajorUnits } from "@/lib/money";
import { getTenantFor } from "@/lib/tenant";

import { BackLink } from "@/components/back-link";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

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
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href={`/quotes/${id}`} label={t("back")} />
      <PageHeader
        title={
          <>
            <span className="tabular-nums text-muted">#{quote.number}</span> {t("edit")}
          </>
        }
      />
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
    </Container>
  );
}
