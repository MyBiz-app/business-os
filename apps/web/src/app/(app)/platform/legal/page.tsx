import type { Metadata } from "next";
import { BRAND } from "@business-os/i18n/brand";
import { getLocale, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";

import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Pill } from "@/components/pill";
import { ScrollRegion } from "@/components/scroll-region";
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
        <ScrollRegion labelledBy="legal-documents" className="card">
          <table className="w-full text-sm">
            <thead className="text-muted">
              <tr className="border-b border-border">
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("document")}</th>
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("version")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("accepted")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("eligible")}</th>
              </tr>
            </thead>
            <tbody>
              {board.documents.map((row) => (
                <tr key={row.document} className="border-b border-border last:border-0">
                  <th scope="row" className="px-4 py-3 text-start font-medium">{t(`documents.${row.document}`)}</th>
                  <td className="px-4 py-3" dir="ltr">{row.version}</td>
                  <td className="px-4 py-3 text-end tabular-nums">{number.format(row.accepted)}</td>
                  <td className="px-4 py-3 text-end tabular-nums">{number.format(row.eligible)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      </section>

      <section aria-labelledby="legal-acceptances" className="flex flex-col gap-3">
        <h2 id="legal-acceptances" className="text-lg font-semibold">{t("acceptancesTitle")}</h2>
        <p className="text-sm text-muted">{t("acceptancesHint", { days: board.days })}</p>
        {board.acceptances.length === 0 ? (
          <EmptyState variant="list">{t("acceptancesEmpty")}</EmptyState>
        ) : (
          <ScrollRegion labelledBy="legal-acceptances" className="card">
            <table className="w-full text-sm">
              <thead className="text-muted">
                <tr className="border-b border-border">
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("person")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("business")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("document")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("context")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("when")}</th>
                </tr>
              </thead>
              <tbody>
                {board.acceptances.map((row, index) => (
                  <tr key={`${row.email}-${row.document}-${row.version}-${index}`} className="border-b border-border last:border-0">
                    <td className="px-4 py-3" dir="ltr">{row.email}</td>
                    <td className="px-4 py-3" dir="auto">{row.business_name ?? "-"}</td>
                    <td className="px-4 py-3">{t(`documents.${row.document}`)} <span className="text-xs text-muted" dir="ltr">{row.version}</span></td>
                    <td className="px-4 py-3">{t(`contexts.${row.context}`)}</td>
                    <td className="px-4 py-3">{stamp.format(new Date(row.accepted_at))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
        )}
      </section>

      <section aria-labelledby="legal-privacy" className="flex flex-col gap-3">
        <h2 id="legal-privacy" className="text-lg font-semibold">{t("privacyTitle")}</h2>
        <p className="text-sm text-muted">{t("privacyHint")}</p>
        {board.privacy_requests.length === 0 ? (
          <EmptyState variant="list">{t("privacyEmpty")}</EmptyState>
        ) : (
          <ScrollRegion labelledBy="legal-privacy" className="card">
            <table className="w-full text-sm">
              <thead className="text-muted">
                <tr className="border-b border-border">
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("kind")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("business")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("status")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("when")}</th>
                </tr>
              </thead>
              <tbody>
                {board.privacy_requests.map((row, index) => (
                  <tr key={`${row.business_id}-${row.kind}-${row.occurred_at}-${index}`} className="border-b border-border last:border-0">
                    <td className="px-4 py-3">{t(`kinds.${row.kind}`)}</td>
                    <td className="px-4 py-3" dir="auto">{row.business_name}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <Pill tone={tone(row.status)}>{t(`statuses.${row.status}`)}</Pill>
                        {row.delete_after ? <span className="text-xs text-muted">{t("deleteAfter", { date: day.format(new Date(row.delete_after)) })}</span> : null}
                      </div>
                    </td>
                    <td className="px-4 py-3">{stamp.format(new Date(row.occurred_at))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
        )}
      </section>
    </Container>
  );
}
