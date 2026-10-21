import { DataTable } from "@/components/ui/data-table";
import type { Metadata } from "next";
import { BRAND } from "@business-os/i18n/brand";
import { getLocale, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";

import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { getPlatform } from "@/lib/platform";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("platform.legal");
  return { title: `${t("title")} · ${BRAND.name}` };
}

const ACCEPTANCE_DAYS = 30;

/** The legal center (K4, owners only): the current version of each document, who accepted it,
 * and the privacy requests (what a lawyer or an auditor asks to see). */
export default async function PlatformLegalPage() {
  const t = await getTranslations("platform.legal");
  const locale = await getLocale();
  const { api, isOwner } = await getPlatform();
  if (!isOwner) notFound();
  const board = unwrap(await api.GET("/platform/legal", { params: { query: { days: ACCEPTANCE_DAYS } } }));
  const number = new Intl.NumberFormat(locale);
  const day = new Intl.DateTimeFormat(locale, { dateStyle: "medium" });
  const stamp = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });
  const tone = (status: string) => (status === "failed" ? "danger" : status === "waiting" ? "warning" : "muted");

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-8 py-8 sm:py-10">
      <PageHeader title={t("title")} description={t("hint")} />

      <section aria-labelledby="legal-documents" className="flex flex-col gap-3">
        <h2 id="legal-documents" className="text-lg font-semibold">{t("documentsTitle")}</h2>
        <DataTable
          labelledBy="legal-documents"
          rows={board.documents}
          rowKey={(row) => row.document}
          columns={[
            { key: "document", header: t("document"), rowHeader: true, cell: (row) => t(`documents.${row.document}`) },
            { key: "version", header: t("version"), cell: (row) => <bdi dir="ltr">{row.version}</bdi> },
            { key: "accepted", header: t("accepted"), align: "end", className: "tabular-nums", cell: (row) => number.format(row.accepted) },
            { key: "eligible", header: t("eligible"), align: "end", className: "tabular-nums", cell: (row) => number.format(row.eligible) },
          ]}
        />
      </section>

      <section aria-labelledby="legal-acceptances" className="flex flex-col gap-3">
        <h2 id="legal-acceptances" className="text-lg font-semibold">{t("acceptancesTitle")}</h2>
        <p className="text-sm text-muted">{t("acceptancesHint", { days: board.days })}</p>
        {board.acceptances.length === 0 ? (
          <EmptyState variant="list">{t("acceptancesEmpty")}</EmptyState>
        ) : (
          <DataTable
            labelledBy="legal-acceptances"
            rows={board.acceptances}
            rowKey={(row, index) => `${row.email}-${row.document}-${row.version}-${index}`}
            columns={[
              { key: "person", header: t("person"), cell: (row) => <bdi dir="ltr">{row.email}</bdi> },
              { key: "business", header: t("business"), cell: (row) => <span dir="auto">{row.business_name ?? "-"}</span> },
              {
                key: "document",
                header: t("document"),
                cell: (row) => (
                  <>
                    {t(`documents.${row.document}`)} <span className="text-xs text-muted" dir="ltr">{row.version}</span>
                  </>
                ),
              },
              { key: "context", header: t("context"), cell: (row) => t(`contexts.${row.context}`) },
              { key: "when", header: t("when"), cell: (row) => stamp.format(new Date(row.accepted_at)) },
            ]}
          />
        )}
      </section>

      <section aria-labelledby="legal-privacy" className="flex flex-col gap-3">
        <h2 id="legal-privacy" className="text-lg font-semibold">{t("privacyTitle")}</h2>
        <p className="text-sm text-muted">{t("privacyHint")}</p>
        {board.privacy_requests.length === 0 ? (
          <EmptyState variant="list">{t("privacyEmpty")}</EmptyState>
        ) : (
          <DataTable
            labelledBy="legal-privacy"
            rows={board.privacy_requests}
            rowKey={(row, index) => `${row.business_id}-${row.kind}-${row.occurred_at}-${index}`}
            columns={[
              { key: "kind", header: t("kind"), cell: (row) => t(`kinds.${row.kind}`) },
              { key: "business", header: t("business"), cell: (row) => <span dir="auto">{row.business_name}</span> },
              {
                key: "status",
                header: t("status"),
                cell: (row) => (
                  <div className="flex flex-wrap items-center gap-2">
                    <Pill tone={tone(row.status)}>{t(`statuses.${row.status}`)}</Pill>
                    {row.delete_after ? <span className="text-xs text-muted">{t("deleteAfter", { date: day.format(new Date(row.delete_after)) })}</span> : null}
                  </div>
                ),
              },
              { key: "when", header: t("when"), cell: (row) => stamp.format(new Date(row.occurred_at)) },
            ]}
          />
        )}
      </section>
    </Container>
  );
}
