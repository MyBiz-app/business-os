import { Check, Plug, X } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { Pill, type Tone } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { isolate } from "@/lib/bidi";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { TopicHeader } from "../topic-header";

import { decideRequest, disconnectApp } from "./actions";
import { CollapsibleSection } from "@/components/ui/collapsible-section";

const TONE: Record<string, Tone> = { pending: "warning", executed: "success", rejected: "muted", expired: "muted", failed: "danger" };
const DETAILS = ["client", "service", "starts", "dependent", "date", "hours", "description", "month", "clients", "total", "body", "reason"] as const;

/** Settings → AI connections (R37b): Claude and ChatGPT connected to the business, the changes
 * they suggested (each waits here for approval), and how to connect another app. */
export default async function AiConnectionsPage() {
  const t = await getTranslations("aiConnections");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenant();
  if (!canManageSettings(tenant)) redirect("/dashboard");
  const [connections, requests, info] = await Promise.all([
    api.GET("/mcp-connections", { params: scope }).then(unwrap),
    api.GET("/mcp-requests", { params: scope }).then(unwrap),
    api.GET("/mcp-info", { params: scope }).then(unwrap),
  ]);
  const stamp = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short", timeZone: tenant.time_zone });
  const waiting = requests.filter((r) => r.status === "pending");
  const recent = requests.filter((r) => r.status !== "pending");
  const label = (request: (typeof requests)[number]) => t.has(`kinds.${request.tool_name}`) ? t(`kinds.${request.tool_name}`) : request.tool_name;

  return (
    <div className="form-columns">
      <TopicHeader title={t("title")} description={t("subtitle")} />

      <section aria-labelledby="ai-waiting" className="flex flex-col gap-3">
        <h3 id="ai-waiting" className="text-lg font-semibold">{t("waitingTitle")}</h3>
        <p className="text-sm text-muted">{t("waitingHint")}</p>
        {waiting.length === 0 ? (
          <p className="card p-5 text-sm text-muted">{t("waitingEmpty")}</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {waiting.map((request) => {
              const what = label(request);
              const preview = request.preview as Record<string, unknown>;
              return (
                <li key={request.id} className="flex flex-col gap-3 card p-5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h4 className="font-semibold">{what}</h4>
                    <span className="text-xs text-muted">
                      {request.client_name ? t("from", { app: isolate(request.client_name) }) : ""} · {t("expires", { when: stamp.format(new Date(request.expires_at)) })}
                    </span>
                  </div>
                  <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-2">
                    {DETAILS.filter((key) => preview[key] !== undefined && preview[key] !== null && preview[key] !== "").map((key) => (
                      <div key={key} className="flex gap-2">
                        <dt className="text-muted">{t(`fields.${key}`)}</dt>
                        <dd dir="auto" className="min-w-0 break-words">{isolate(String(preview[key]))}</dd>
                      </div>
                    ))}
                  </dl>
                  {preview.full === true && <p className="text-sm text-warning">{t("full")}</p>}
                  <div className="flex flex-wrap gap-2">
                    <form action={decideRequest.bind(null, request.id, "confirm")}>
                      <button type="submit" className="btn-primary inline-flex items-center gap-1.5 px-4 py-2" aria-label={t("approveFor", { what })}>
                        <Check aria-hidden="true" className="size-4" />
                        {t("approve")}
                      </button>
                    </form>
                    <form action={decideRequest.bind(null, request.id, "reject")}>
                      <button type="submit" className="btn-secondary inline-flex items-center gap-1.5 px-4 py-2" aria-label={t("rejectFor", { what })}>
                        <X aria-hidden="true" className="size-4" />
                        {t("reject")}
                      </button>
                    </form>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        {recent.length > 0 && (
          <CollapsibleSection title={t("historyTitle")} storageKey="ai-connections-history">
            <ul className="flex flex-col gap-2 text-sm">
              {recent.map((request) => (
                <li key={request.id} className="flex flex-wrap items-center justify-between gap-2">
                  <span dir="auto">
                    {label(request)}
                    {typeof request.preview.client === "string" ? `: ${isolate(request.preview.client)}` : ""}
                  </span>
                  <span className="flex items-center gap-2 text-muted">
                    {stamp.format(new Date(request.created_at))}
                    <Pill tone={TONE[request.status] ?? "muted"}>{t(`status.${request.status}`)}</Pill>
                  </span>
                </li>
              ))}
            </ul>
          </CollapsibleSection>
        )}
      </section>

      <section aria-labelledby="ai-apps" className="flex flex-col gap-3">
        <h3 id="ai-apps" className="text-lg font-semibold">{t("appsTitle")}</h3>
        {connections.length === 0 ? (
          <p className="card p-5 text-sm text-muted">{t("appsEmpty")}</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {connections.map((connection) => (
              <li key={connection.id} className="flex flex-wrap items-center justify-between gap-3 card p-5">
                <div className="flex min-w-0 flex-col gap-1">
                  <span className="flex items-center gap-2 font-semibold">
                    <Plug aria-hidden="true" className="size-4 text-primary-ink" />
                    <bdi>{connection.client_name}</bdi>
                    <Pill tone={connection.can_propose ? "primary" : "muted"}>{connection.can_propose ? t("canPropose") : t("readOnly")}</Pill>
                  </span>
                  <span className="text-sm text-muted">
                    {connection.last_used_at ? t("lastUsed", { when: stamp.format(new Date(connection.last_used_at)) }) : t("neverUsed")} · {t("calls", { count: connection.calls })}
                  </span>
                </div>
                <form action={disconnectApp.bind(null, connection.id)}>
                  <button type="submit" className="btn-link text-sm text-danger underline-offset-4 hover:underline" aria-label={t("disconnectApp", { app: connection.client_name })}>
                    {t("disconnect")}
                  </button>
                </form>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="ai-how" className="flex flex-col gap-4">
        <h3 id="ai-how" className="text-lg font-semibold">{t("howTitle")}</h3>
        <p className="text-sm text-muted">{t("howIntro")}</p>
        <div className="flex flex-col gap-1 card p-5">
          <span className="text-sm font-medium">{t("address")}</span>
          <code dir="ltr" className="select-all break-all rounded-lg bg-surface px-3 py-2 text-sm">{info.url}</code>
          <span className="text-xs text-muted">{t("addressHint")}</span>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {(["claude", "chatgpt"] as const).map((app) => (
            <div key={app} className="flex flex-col gap-2 card p-5">
              <h4 className="font-semibold">{t(`${app}Title`)}</h4>
              <ol className="list-decimal ps-5 text-sm [&>li]:py-0.5">
                {(t.raw(`${app}Steps`) as string[]).map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="ai-safety" className="flex flex-col gap-2">
        <h3 id="ai-safety" className="text-lg font-semibold">{t("safetyTitle")}</h3>
        <ul className="list-disc ps-5 text-sm text-muted">
          {(t.raw("safety") as string[]).map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
