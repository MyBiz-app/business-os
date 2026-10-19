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
  const t = await getTranslations("platform.security");
  return { title: `${t("title")} · ${BRAND.name}` };
}

const VISIT_DAYS = 30;

/** The security center (K4, owners only): two-step sign-in of business owners, the MyBiz team's
 * visits inside businesses and the saved reports of the security agent. */
export default async function PlatformSecurityPage() {
  const t = await getTranslations("platform.security");
  const locale = await getLocale();
  const { api, isOwner } = await getPlatform();
  if (!isOwner) notFound();
  const [owners, visits, findings] = await Promise.all([
    api.GET("/platform/security/owners").then(unwrap),
    api.GET("/platform/security/visits", { params: { query: { days: VISIT_DAYS } } }).then(unwrap),
    api.GET("/platform/ai/reports", { params: { query: { kind: "security", limit: 10 } } }).then(unwrap),
  ]);
  const number = new Intl.NumberFormat(locale);
  const day = new Intl.DateTimeFormat(locale, { dateStyle: "medium" });
  const stamp = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });
  const count = (value: number | null) => (value === null ? t("unknown") : number.format(value));

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-8 py-8 sm:py-10">
      <PageHeader title={t("title")} description={t("hint")} />

      {owners.with_mfa === null ? (
        <p role="status" className="card p-4 text-sm text-muted">{t("unknownNote")}</p>
      ) : null}

      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { label: t("owners"), value: count(owners.owners), alarm: false },
          { label: t("withMfa"), value: count(owners.with_mfa), alarm: false },
          { label: t("acknowledged"), value: count(owners.acknowledged_risk), alarm: false },
          { label: t("exposed"), value: count(owners.exposed), alarm: (owners.exposed ?? 0) > 0 },
        ].map((fact) => (
          <div key={fact.label} className="card flex flex-col gap-1 p-5">
            <dt className="text-sm text-muted">{fact.label}</dt>
            <dd className={`text-2xl font-semibold ${fact.alarm ? "text-danger" : ""}`} dir="ltr">{fact.value}</dd>
          </div>
        ))}
      </dl>
      <p className="text-sm text-muted">
        {t("requiring")}: <span dir="ltr">{number.format(owners.businesses_requiring_mfa)} / {number.format(owners.businesses)}</span>
      </p>

      <section aria-labelledby="security-owners" className="flex flex-col gap-3">
        <h2 id="security-owners" className="text-lg font-semibold">{t("ownersTitle")}</h2>
        <p className="text-sm text-muted">{t("ownersHint", { version: owners.risk_version })}</p>
        {owners.rows.length === 0 ? (
          <EmptyState variant="list">{t("ownersEmpty")}</EmptyState>
        ) : (
          <ScrollRegion labelledBy="security-owners" className="card">
            <table className="w-full text-sm">
              <thead className="text-muted">
                <tr className="border-b border-border">
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("owner")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("business")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("protection")}</th>
                </tr>
              </thead>
              <tbody>
                {owners.rows.map((row) => (
                  <tr key={`${row.business_id}-${row.email}`} className="border-b border-border last:border-0">
                    <td className="px-4 py-3" dir="ltr">{row.email}</td>
                    <td className="px-4 py-3" dir="auto">{row.business_name}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap items-center gap-2">
                        {row.mfa_enrolled === null ? (
                          <Pill tone="muted">{t("unknown")}</Pill>
                        ) : row.mfa_enrolled ? (
                          <Pill tone="success">{t("on")}</Pill>
                        ) : (
                          <Pill tone={row.risk_acknowledged_at ? "warning" : "danger"}>{t("off")}</Pill>
                        )}
                        {row.mfa_enrolled ? null : (
                          <span className="text-xs text-muted">
                            {row.risk_acknowledged_at ? t("confirmed", { date: day.format(new Date(row.risk_acknowledged_at)) }) : t("notConfirmed")}
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
        )}
      </section>

      <section aria-labelledby="security-visits" className="flex flex-col gap-3">
        <h2 id="security-visits" className="text-lg font-semibold">{t("visitsTitle")}</h2>
        <p className="text-sm text-muted">{t("visitsHint", { days: visits.days })}</p>
        {visits.visits.length === 0 ? (
          <EmptyState variant="list">{t("visitsEmpty")}</EmptyState>
        ) : (
          <ScrollRegion labelledBy="security-visits" className="card">
            <table className="w-full text-sm">
              <thead className="text-muted">
                <tr className="border-b border-border">
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("member")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("business")}</th>
                  <th scope="col" className="px-4 py-3 text-end font-medium">{t("views")}</th>
                  <th scope="col" className="px-4 py-3 text-end font-medium">{t("changes")}</th>
                  <th scope="col" className="px-4 py-3 text-start font-medium">{t("lastVisit")}</th>
                </tr>
              </thead>
              <tbody>
                {visits.visits.map((row) => (
                  <tr key={`${row.business_id}-${row.actor_email}`} className="border-b border-border last:border-0">
                    <td className="px-4 py-3" dir="ltr">{row.actor_email}</td>
                    <td className="px-4 py-3" dir="auto">{row.business_name}</td>
                    <td className="px-4 py-3 text-end tabular-nums">{number.format(row.views)}</td>
                    <td className="px-4 py-3 text-end tabular-nums">{number.format(row.changes)}</td>
                    <td className="px-4 py-3">{stamp.format(new Date(row.last_at))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
        )}
      </section>

      <section aria-labelledby="security-findings" className="flex flex-col gap-3">
        <h2 id="security-findings" className="text-lg font-semibold">{t("findingsTitle")}</h2>
        <p className="text-sm text-muted">{t("findingsHint")}</p>
        {findings.length === 0 ? (
          <EmptyState variant="list">{t("findingsEmpty")}</EmptyState>
        ) : (
          <ul className="flex flex-col gap-3">
            {findings.map((report) => (
              <li key={report.id} className="card flex flex-col gap-1 p-4">
                <span className="font-medium" dir="auto">{report.title}</span>
                <span className="text-sm" dir="auto">{report.summary}</span>
                <span className="text-xs text-muted">{stamp.format(new Date(report.created_at))} · {t("by")} {report.created_by}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </Container>
  );
}
