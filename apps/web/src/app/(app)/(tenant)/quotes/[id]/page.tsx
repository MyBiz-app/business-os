import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Pill } from "@/components/pill";

import { STATUS_TONE } from "../status";
import { loadQuote, QuoteBody } from "./quote-body";

/** One quote: its lines and totals, sending it, the client's answer, payments. */
export default async function QuotePage({ params }: PageProps<"/quotes/[id]">) {
  const { id } = await params;
  const t = await getTranslations("quotes");
  const locale = await getLocale();
  const { tenant, quote } = await loadQuote(id);
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "full", timeStyle: "short", timeZone: tenant.time_zone });

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <Link href="/quotes" className="text-sm text-primary-ink underline-offset-4 hover:underline">{t("back")}</Link>
      <PageHeader
        title={
          <>
            <span className="tabular-nums text-muted">#{quote.number}</span> <span dir="auto">{quote.title}</span>
          </>
        }
        description={
          <>
            <Link href={`/clients/${quote.client_id}`} dir="auto" className="underline-offset-4 hover:underline">{quote.client_name}</Link>
            {quote.event_starts_at && ` · ${when.format(new Date(quote.event_starts_at))}`}
            {quote.event_place && <span dir="auto"> · {quote.event_place}</span>}
          </>
        }
        actions={<Pill tone={STATUS_TONE[quote.status]}>{t(`statuses.${quote.status}`)}</Pill>}
      />
      <QuoteBody id={id} />
    </Container>
  );
}
