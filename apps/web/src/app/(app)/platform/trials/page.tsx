import { DataTable } from "@/components/ui/data-table";
import { getFormatter, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Ltr, UserText } from "@/components/bidi";
import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Pill } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { getPlatformFor } from "@/lib/platform";

import { ExtendForm } from "./extend-form";

const RANGES = [7, 14, 30] as const;

/** Trials that end soon (and the last three days), with quick actions: write to the owner, extend,
 * open the business card. This is the moment a business decides whether to pay (K2). */
export default async function TrialsPage({ searchParams }: PageProps<"/platform/trials">) {
  const t = await getTranslations("platform.trials");
  const format = await getFormatter();
  const { api, can } = await getPlatformFor("businesses.read");
  const query = await searchParams;
  const asked = Number(Array.isArray(query.days) ? query.days[0] : query.days);
  const days = RANGES.find((range) => range === asked) ?? 7;
  const rows = unwrap(await api.GET("/platform/trials-ending", { params: { query: { days } } }));
  const now = new Date();
  const mayExtend = can("billing.manage");

  return (
    <Container as="main" size="default" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader title={t("title")} description={t("hint")} />
      <nav aria-label={t("title")} className="flex flex-wrap gap-2">
        {RANGES.map((range) => (
          <Link
            key={range}
            href={`/platform/trials?days=${range}`}
            scroll={false}
            aria-current={range === days ? "page" : undefined}
            className={range === days ? "btn-primary px-3 py-1.5 text-sm" : "btn-secondary px-3 py-1.5 text-sm"}
          >
            {t("range", { days: range })}
          </Link>
        ))}
      </nav>
      {rows.length === 0 ? (
        <EmptyState variant="list">{t("empty")}</EmptyState>
      ) : (
        <>
          <h2 id="trials-title" className="sr-only">
            {t("title")}
          </h2>
          <DataTable
            labelledBy="trials-title"
            rows={rows}
            rowKey={(row) => row.tenant_id}
            rowClassName={() => "align-top"}
            columns={[
              {
                key: "business",
                header: t("business"),
                rowHeader: true,
                cell: (row) => (
                  <>
                    <Link href={`/platform/businesses/${row.tenant_id}`} className="underline-offset-4 hover:underline">
                      <UserText>{row.name}</UserText>
                    </Link>
                    {row.owner_email && (
                      <div className="font-normal text-muted">
                        <Ltr>{row.owner_email}</Ltr>
                      </div>
                    )}
                  </>
                ),
              },
              {
                key: "ends",
                header: t("ends"),
                cell: (row) => {
                  const ends = new Date(row.trial_ends_at);
                  const date = format.dateTime(ends, { dateStyle: "medium" });
                  return <Pill tone={ends < now ? "danger" : "warning"}>{ends < now ? t("ended", { date }) : t("endsOn", { date })}</Pill>;
                },
              },
              { key: "clients", header: t("clients"), align: "end", className: "tabular-nums", cell: (row) => format.number(row.active_clients) },
              { key: "card", header: t("card"), cell: (row) => <Pill tone={row.has_card ? "success" : "muted"}>{row.has_card ? t("cardYes") : t("cardNo")}</Pill> },
              { key: "accountOwner", header: t("accountOwner"), cell: (row) => (row.account_owner ? <Ltr>{row.account_owner}</Ltr> : "-") },
              {
                key: "actions",
                header: t("actions"),
                cell: (row) => (
                  <div className="flex flex-col gap-2">
                    <div className="flex flex-wrap gap-3">
                      {row.owner_email && (
                        <a href={`mailto:${row.owner_email}`} className="text-primary-ink underline-offset-4 hover:underline">
                          {t("message")}
                        </a>
                      )}
                      <Link href={`/platform/businesses/${row.tenant_id}`} className="text-primary-ink underline-offset-4 hover:underline">
                        {t("open")}
                      </Link>
                    </div>
                    {mayExtend && <ExtendForm tenantId={row.tenant_id} />}
                  </div>
                ),
              },
            ]}
          />
        </>
      )}
    </Container>
  );
}
