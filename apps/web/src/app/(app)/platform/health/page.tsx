import type { Metadata } from "next";
import { BRAND } from "@business-os/i18n/brand";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { ScrollRegion } from "@/components/scroll-region";
import { unwrap } from "@/lib/api";
import { getPlatformFor } from "@/lib/platform";

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
        <dl className="grid gap-3 sm:grid-cols-3">
          {facts.map((fact) => (
            <div key={fact.label} className="card flex flex-col gap-1 p-5">
              <dt className="text-sm text-muted">{fact.label}</dt>
              <dd className={`text-2xl font-semibold ${fact.alarm ? "text-danger" : ""}`} dir="ltr">{fact.value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="health-jobs" className="flex flex-col gap-4">
        <h2 id="health-jobs" className="text-lg font-semibold">{t("jobs")}</h2>
        {health.jobs.length === 0 ? (
          <EmptyState variant="list">{t("noJobs")}</EmptyState>
        ) : (
          <ScrollRegion labelledBy="health-jobs" className="rounded-2xl border border-border">
            <table className="w-full text-sm">
              <thead className="bg-surface text-muted">
                <tr>
                  {(["job", "status", "lastOk", "lastRun", "runs", "failures"] as const).map((key) => (
                    <th key={key} scope="col" className="px-4 py-3 text-start font-medium">{t(key)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {health.jobs.map((job) => {
                  const state = jobState(job);
                  return (
                    <tr key={job.job} className="border-t border-border align-top">
                      <td className="px-4 py-2.5 font-medium" dir="ltr">{job.job}</td>
                      <td className={`px-4 py-2.5 font-medium ${tone[state]}`}>
                        {t(state)}
                        {state === "failed" && job.last_result && (
                          <span className="block max-w-xs truncate text-xs font-normal text-muted" dir="ltr" title={job.last_result}>{job.last_result}</span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-4 py-2.5">{at(job.last_ok_at)}</td>
                      <td className="whitespace-nowrap px-4 py-2.5">{at(job.last_run_at)}</td>
                      <td className="px-4 py-2.5">{job.runs_24h}</td>
                      <td className="px-4 py-2.5">{job.failures_24h}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </ScrollRegion>
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
          <ScrollRegion labelledBy="health-routes" className="rounded-2xl border border-border">
            <table className="w-full text-sm">
              <thead className="bg-surface text-muted">
                <tr>
                  {(["route", "count", "p50", "p95"] as const).map((key) => (
                    <th key={key} scope="col" className="px-4 py-3 text-start font-medium">{t(key)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {health.routes.map((route) => (
                  <tr key={route.route} className="border-t border-border">
                    <td className="px-4 py-2.5" dir="ltr">{route.route}</td>
                    <td className="px-4 py-2.5">{route.count}</td>
                    <td className="px-4 py-2.5">{number.format(route.p50_ms)}</td>
                    <td className="px-4 py-2.5">{number.format(route.p95_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
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
          <ScrollRegion labelledBy="health-errors" className="rounded-2xl border border-border">
            <table className="w-full text-sm">
              <thead className="bg-surface text-muted">
                <tr>
                  {(["when", "requestId", "path", "business"] as const).map((key) => (
                    <th key={key} scope="col" className="px-4 py-3 text-start font-medium">{t(key)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {health.errors.map((error, index) => (
                  <tr key={`${error.at}-${index}`} className="border-t border-border">
                    <td className="whitespace-nowrap px-4 py-2.5">{when.format(new Date(error.at))}</td>
                    <td className="px-4 py-2.5" dir="ltr">{error.request_id ?? "-"}</td>
                    <td className="px-4 py-2.5" dir="ltr">{error.method} {error.path ?? "-"} {error.error ? `(${error.error})` : ""}</td>
                    <td className="px-4 py-2.5" dir="ltr">
                      {error.tenant_id ? (
                        <Link href={`/platform/businesses/${error.tenant_id}`} className="text-primary-ink underline-offset-4 hover:underline">
                          {error.tenant_id.slice(0, 8)}
                        </Link>
                      ) : (
                        "-"
                      )}
                    </td>
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
