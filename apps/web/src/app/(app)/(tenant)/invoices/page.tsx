import { FileText, Plus } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Ltr } from "@/components/bidi";
import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { LinkSegmented } from "@/components/ui/link-segmented";
import { PageHeader } from "@/components/layout/page-header";
import { SummaryTiles } from "@/components/ui/summary-tiles";
import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { DOCUMENT_KINDS } from "@/lib/issued-documents";
import { formatMoney } from "@/lib/money";
import { getTenantFor } from "@/lib/tenant";
import { CardTransition } from "@/components/ui/page-transition";

/** The documents the business has issued to its clients, newest first, with the number each
 * kind gets next. */
export default async function InvoicesPage({ searchParams }: PageProps<"/invoices">) {
  const t = await getTranslations("invoices");
  const tc = await getTranslations("common");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("sales.manage");
  const raw = (await searchParams).kind;
  const filter = DOCUMENT_KINDS.find((k) => k === raw);
  const [documents, recent, series] = await Promise.all([
    api.GET("/issued-documents", { params: { ...scope, query: filter ? { kind: filter, limit: 100 } : { limit: 100 } } }).then(unwrap),
    // The tiles always count the latest documents of every kind, whichever kind the list shows.
    filter ? api.GET("/issued-documents", { params: { ...scope, query: { limit: 100 } } }).then(unwrap) : Promise.resolve(null),
    api.GET("/issued-documents/series", { params: scope }).then(unwrap),
  ]);
  const counted = recent ?? documents;
  const tiles = DOCUMENT_KINDS.flatMap((kind) => {
    const rows = counted.filter((doc) => doc.kind === kind);
    if (rows.length === 0 && filter !== kind) return [];
    const currencies = new Set(rows.map((doc) => doc.currency));
    return [
      {
        key: kind,
        label: t(`kinds.${kind}`),
        value: `${rows.length}${counted.length >= 100 ? "+" : ""}`,
        hint: rows.length > 0 && currencies.size === 1 ? formatMoney(rows.reduce((sum, doc) => sum + doc.total, 0), [...currencies][0], locale) : undefined,
        href: `/invoices?kind=${kind}`,
        active: filter === kind,
      },
    ];
  });
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: tenant.time_zone });

  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader
        title={
          <span className="flex items-center gap-3">
            <FileText aria-hidden="true" className="size-8 shrink-0 text-primary-ink" />
            {t("title")}
          </span>
        }
        description={t("subtitle")}
        actions={
          <Link href="/invoices/new" className="btn-primary px-4 py-2">
            <Plus aria-hidden="true" className="size-4" /> {t("new")}
          </Link>
        }
      />
      <LinkSegmented
        variant="chips"
        label={t("filter")}
        loadingLabel={tc("loading")}
        active={filter ?? "all"}
        options={[undefined, ...DOCUMENT_KINDS].map((k) => ({ key: k ?? "all", label: k ? t(`kinds.${k}`) : t("all"), href: k ? `/invoices?kind=${k}` : "/invoices" }))}
      />
      {tiles.length > 0 && <SummaryTiles label={t("tiles.label")} tiles={tiles} />}
      {documents.length === 0 ? (
        <EmptyState variant="list">{t("none")}</EmptyState>
      ) : (
        <ul className="flex flex-col divide-y divide-border card">
          {documents.map((doc) => (
            <li key={doc.id}>
              <CardTransition name={`invoice-${doc.id}`}>
<Link href={`/invoices/${doc.id}`} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 hover:bg-foreground/[0.03]">
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span className="font-semibold">
                    {t(`kinds.${doc.kind}`)} <Ltr className="tabular-nums text-muted">#{doc.number}</Ltr>
                  </span>
                  <span className="text-sm text-muted">
                    <span dir="auto">{doc.client_name}</span> · {date.format(new Date(doc.issued_at))}
                  </span>
                </span>
                <span className="flex items-center gap-3">
                  {doc.allocation_required && !doc.allocation_number && <Pill tone="warning">{t("allocationPending")}</Pill>}
                  <span className="font-semibold tabular-nums">
                    <bdi>{formatMoney(doc.total, doc.currency, locale)}</bdi>
                  </span>
                </span>
              </Link>
</CardTransition>
            </li>
          ))}
        </ul>
      )}
      <section aria-labelledby="series-heading" className="card flex flex-col gap-3 p-6">
        <h2 id="series-heading" className="text-sm font-medium text-muted">{t("nextNumbers")}</h2>
        <ul className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
          {series.map((s) => (
            <li key={s.kind}>
              {t(`kinds.${s.kind}`)} <Ltr className="font-semibold tabular-nums">{s.next_number}</Ltr>
            </li>
          ))}
        </ul>
      </section>
    </Container>
  );
}
