import { DataTable } from "@/components/ui/data-table";
import type { Metadata } from "next";
import { BRAND } from "@business-os/i18n/brand";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { unwrap } from "@/lib/api";
import { getPlatformFor } from "@/lib/platform";
import { StatTile } from "@/components/ui/stat-tile";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("platform.health");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** System health (go-live GL13): background jobs, queues, size, AI spend and the latest crashes. */
export default async function PlatformHealthPage() {
  const t = await getTranslations("platform.health");
  const locale = await getLocale();
  const { api } = await getPlatformFor("usage.read");
  const health = unwrap(await api.GET("/platform/health"));
  const when = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" });
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  const at = (value: string | null | undefined) => (value ? when.format(new Date(value)) : t("never"));
  const megabytes = `${number.format(health.database_bytes / (1024 * 1024))} MB`;
  const jobState = (job: (typeof health.jobs)[number]) =>
    job.late ? "late" : job.last_ok === false ? "failed" : "ok";
  const tone = { ok: "text-success", late: "text-danger", failed: "text-danger" } as const;

  const facts: { label: string; value: string; alarm?: boolean }[] = [
    { label: t("messagesQueued"), value: number.format(health.messages_queued) },
    { label: t("messagesFailed"), value: number.format(health.messages_failed_24h), alarm: health.messages_failed_24h > 0 },
    { label: t("emailsWaiting"), value: number.format(health.emails_waiting) },
    { label: t("database"), value: megabytes },
    { label: t("files"), value: `${number.format(health.files_bytes / (1024 * 1024))} MB` },
    {
      label: t("aiToday"),
      value: `${number.format(health.ai_credits_today)} ${t("aiLimit", { limit: number.format(health.ai_alert_at) })}`,
      alarm: health.ai_alert_at > 0 && health.ai_credits_today >= health.ai_alert_at,
    },
    ...(health.release ? [{ label: t("release"), value: health.release.slice(0, 7) }] : []),
  ];

  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-8 py-8 sm:py-10">
      <PageHeader titleId="health-heading" title={t("title")} description={t("subtitle")} />

      <section aria-labelledby="health-queues" className="flex flex-col gap-4">
        <h2 id="health-queues" className="text-lg font-semibold">{t("queues")}</h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {facts.map((fact) => (
            <StatTile key={fact.label} label={fact.label} value={<span className={fact.alarm ? "text-danger" : undefined} dir="ltr">{fact.value}</span>} />
          ))}
        </div>
      </section>

      <section aria-labelledby="health-jobs" className="flex flex-col gap-4">
        <h2 id="health-jobs" className="text-lg font-semibold">{t("jobs")}</h2>
        {health.jobs.length === 0 ? (
          <EmptyState variant="list">{t("noJobs")}</EmptyState>
        ) : (
          <DataTable
            labelledBy="health-jobs"
            rows={health.jobs}
            rowKey={(job) => job.job}
            rowClassName={() => "align-top"}
            columns={[
              { key: "job", header: t("job"), className: "font-medium", cell: (job) => <bdi dir="ltr">{job.job}</bdi> },
              {
                key: "status",
                header: t("status"),
                className: "font-medium",
                cell: (job) => {
                  const state = jobState(job);
                  return (
                    <span className={tone[state]}>
                      {t(state)}
                      {state === "failed" && job.last_result && (
                        <span className="block max-w-xs truncate text-xs font-normal text-muted" dir="ltr" title={job.last_result}>{job.last_result}</span>
                      )}
                    </span>
                  );
                },
              },
              { key: "lastOk", header: t("lastOk"), nowrap: true, cell: (job) => at(job.last_ok_at) },
              { key: "lastRun", header: t("lastRun"), nowrap: true, cell: (job) => at(job.last_run_at) },
              { key: "runs", header: t("runs"), cell: (job) => job.runs_24h },
              { key: "failures", header: t("failures"), cell: (job) => job.failures_24h },
            ]}
          />
        )}
      </section>

      <section aria-labelledby="health-routes" className="flex flex-col gap-4">
        <div>
          <h2 id="health-routes" className="text-lg font-semibold">{t("routes")}</h2>
          <p className="text-sm text-muted">{t("routesNote")}</p>
        </div>
        {health.routes.length === 0 ? (
          <EmptyState variant="list">{t("noRoutes")}</EmptyState>
        ) : (
          <DataTable
            labelledBy="health-routes"
            rows={health.routes}
            rowKey={(route) => route.route}
            columns={[
              { key: "route", header: t("route"), cell: (route) => <bdi dir="ltr">{route.route}</bdi> },
              { key: "count", header: t("count"), cell: (route) => route.count },
              { key: "p50", header: t("p50"), cell: (route) => number.format(route.p50_ms) },
              { key: "p95", header: t("p95"), cell: (route) => number.format(route.p95_ms) },
            ]}
          />
        )}
      </section>

      <section aria-labelledby="health-errors" className="flex flex-col gap-4">
        <div>
          <h2 id="health-errors" className="text-lg font-semibold">{t("errors")}</h2>
          <p className="text-sm text-muted">{t("errorsNote")}</p>
        </div>
        {health.errors.length === 0 ? (
          <EmptyState variant="list">{t("noErrors")}</EmptyState>
        ) : (
          <DataTable
            labelledBy="health-errors"
            rows={health.errors}
            rowKey={(error, index) => `${error.at}-${index}`}
            columns={[
              { key: "when", header: t("when"), nowrap: true, cell: (error) => when.format(new Date(error.at)) },
              { key: "requestId", header: t("requestId"), cell: (error) => <bdi dir="ltr">{error.request_id ?? "-"}</bdi> },
              { key: "path", header: t("path"), cell: (error) => <bdi dir="ltr">{error.method} {error.path ?? "-"} {error.error ? `(${error.error})` : ""}</bdi> },
              {
                key: "business",
                header: t("business"),
                cell: (error) =>
                  error.tenant_id ? (
                    <Link dir="ltr" href={`/platform/businesses/${error.tenant_id}`} className="text-primary-ink underline-offset-4 hover:underline">
                      {error.tenant_id.slice(0, 8)}
                    </Link>
                  ) : (
                    "-"
                  ),
              },
            ]}
          />
        )}
      </section>
    </Container>
  );
}
