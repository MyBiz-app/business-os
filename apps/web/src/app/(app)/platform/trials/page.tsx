import { getFormatter, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Ltr, UserText } from "@/components/bidi";
import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { Pill } from "@/components/pill";
import { ScrollRegion } from "@/components/scroll-region";
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
        <ScrollRegion labelledBy="trials-title" className="card">
          <h2 id="trials-title" className="sr-only">
            {t("title")}
          </h2>
          <table className="w-full text-sm">
            <thead className="text-muted">
              <tr className="border-b border-border">
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("business")}</th>
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("ends")}</th>
                <th scope="col" className="px-4 py-3 text-end font-medium">{t("clients")}</th>
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("card")}</th>
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("accountOwner")}</th>
                <th scope="col" className="px-4 py-3 text-start font-medium">{t("actions")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const ends = new Date(row.trial_ends_at);
                const date = format.dateTime(ends, { dateStyle: "medium" });
                return (
                  <tr key={row.tenant_id} className="border-b border-border align-top last:border-0">
                    <th scope="row" className="px-4 py-3 text-start font-medium">
                      <Link href={`/platform/businesses/${row.tenant_id}`} className="underline-offset-4 hover:underline">
                        <UserText>{row.name}</UserText>
                      </Link>
                      {row.owner_email && (
                        <div className="font-normal text-muted">
                          <Ltr>{row.owner_email}</Ltr>
                        </div>
                      )}
                    </th>
                    <td className="px-4 py-3">
                      <Pill tone={ends < now ? "danger" : "warning"}>
                        {ends < now ? t("ended", { date }) : t("endsOn", { date })}
                      </Pill>
                    </td>
                    <td className="px-4 py-3 text-end tabular-nums">{format.number(row.active_clients)}</td>
                    <td className="px-4 py-3">
                      <Pill tone={row.has_card ? "success" : "muted"}>{row.has_card ? t("cardYes") : t("cardNo")}</Pill>
                    </td>
                    <td className="px-4 py-3">{row.account_owner ? <Ltr>{row.account_owner}</Ltr> : "-"}</td>
                    <td className="px-4 py-3">
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
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </ScrollRegion>
      )}
    </Container>
  );
}
