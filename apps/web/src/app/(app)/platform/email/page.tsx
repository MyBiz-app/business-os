import { DataTable } from "@/components/ui/data-table";
import type { Metadata } from "next";
import { BRAND } from "@business-os/i18n/brand";
import { getLocale, getTranslations } from "next-intl/server";

import { ColumnChart } from "@/components/charts/column-chart";
import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { getPlatformFor } from "@/lib/platform";
import { StatTile } from "@/components/ui/stat-tile";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("platform.emailHealth");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** Email deliverability (K3): addresses that bounced or complained, which are never mailed again. */
export default async function PlatformEmailPage() {
  const t = await getTranslations("platform.emailHealth");
  const tRoot = await getTranslations();
  const locale = await getLocale();
  const { api } = await getPlatformFor("usage.read");
  const board = unwrap(await api.GET("/platform/metrics/email"));
  const number = new Intl.NumberFormat(locale);
  const monthLabel = (value: string) => formatDay(value, locale, { month: "short", year: "2-digit" });

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-8 py-8 sm:py-10">
      <PageHeader title={t("title")} description={t("hint")} />

      {board.webhook_open ? null : (
        <p role="status" className="card p-4 text-sm text-danger">{t("webhookClosed")}</p>
      )}

      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { label: t("bounced"), value: board.bounced, alarm: false },
          { label: t("complained"), value: board.complained, alarm: board.complained > 0 },
          { label: t("waiting"), value: board.emails_waiting, alarm: false },
        ].map((fact) => (
          <StatTile key={fact.label} label={fact.label} value={<span className={fact.alarm ? "text-danger" : undefined} dir="ltr">{number.format(fact.value)}</span>} />
        ))}
      </div>

      <section aria-labelledby="email-chart" className="card flex flex-col gap-3 p-4">
        <h2 id="email-chart" className="sr-only">{t("chart")}</h2>
        <ColumnChart
          title={t("chart")}
          unit={{ kind: "count" }}
          tableLabel={tRoot("dashboard.showTable")}
          headers={[t("month"), t("blocked")]}
          columns={board.months.map((m) => ({ key: m.month, label: monthLabel(m.month), value: m.bounced + m.complained, display: String(m.bounced + m.complained) }))}
        />
      </section>

      <section aria-labelledby="email-recent" className="flex flex-col gap-3">
        <h2 id="email-recent" className="text-lg font-semibold">{t("recent")}</h2>
        {board.recent.length === 0 ? (
          <EmptyState variant="list">{t("empty")}</EmptyState>
        ) : (
          <DataTable
            labelledBy="email-recent"
            rows={board.recent}
            rowKey={(row, index) => `${row.address}-${index}`}
            columns={[
              { key: "address", header: t("address"), cell: (row) => <bdi dir="ltr">{row.address}</bdi> },
              { key: "reason", header: t("reason"), cell: (row) => <Pill tone={row.reason === "complained" ? "danger" : "warning"}>{t(`reasons.${row.reason}`)}</Pill> },
              { key: "when", header: t("when"), cell: (row) => formatDay(row.created_at, locale, { day: "numeric", month: "numeric", year: "numeric" }) },
            ]}
          />
        )}
      </section>
    </Container>
  );
}
