import type { components } from "@business-os/api-client";
import { getLocale, getTranslations } from "next-intl/server";

import { Pill, type Tone } from "@/components/pill";
import { unwrap } from "@/lib/api";
import { canWriteClients } from "@/lib/permissions";
import type { getTenant } from "@/lib/tenant";

import { reviewDeclaration } from "./health-actions";

type HealthState = components["schemas"]["ClientHealth"]["state"];

export const HEALTH_TONE: Record<HealthState, Tone> = {
  ok: "success",
  expiring: "primary",
  needs_review: "danger",
  rejected: "danger",
  expired: "muted",
  missing: "muted",
};

type Props = { clientId: string; context: Awaited<ReturnType<typeof getTenant>> };

/** The client's health declaration: state, the signed answers, and the studio's review. */
export async function HealthSection({ clientId, context }: Props) {
  const t = await getTranslations("health");
  const locale = await getLocale();
  const { tenant, api, scope } = context;
  const health = unwrap(
    await api.GET("/clients/{client_id}/health-declarations", {
      params: { ...scope, path: { client_id: clientId } },
    }),
  );
  const [latest] = health.declarations;
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: tenant.time_zone });
  const day = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: "UTC" });
  const yes = latest ? latest.answers.filter((answer) => answer.answer) : [];
  const reviewable = latest?.status === "needs_review" && canWriteClients(tenant);

  return (
    <section aria-labelledby="health-heading" className="flex flex-col gap-4 card p-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 id="health-heading" className="text-lg font-semibold">
          {t("title")}
        </h2>
        <Pill tone={HEALTH_TONE[health.state]}>{t(`states.${health.state}`)}</Pill>
      </div>

      {!latest ? (
        <p className="text-sm text-muted">{tenant.requires_health_declaration ? t("missingRequired") : t("missing")}</p>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-muted">
            {t("signed", {
              name: latest.signed_name,
              date: date.format(new Date(latest.signed_at)),
              until: day.format(new Date(`${latest.valid_until}T12:00:00Z`)),
            })}
          </p>
          {yes.length === 0 ? (
            <p className="text-sm">{t("allClear")}</p>
          ) : (
            <div className="flex flex-col gap-1">
              <h3 className="font-semibold">{t("answeredYes")}</h3>
              <ul className="list-disc ps-5 text-sm" dir="auto">
                {yes.map((answer) => (
                  <li key={answer.id}>{answer.question}</li>
                ))}
              </ul>
            </div>
          )}
          {latest.review_note && (
            <p className="text-sm text-muted" dir="auto">
              {t("reviewNote", { note: latest.review_note })}
            </p>
          )}
          <details className="text-sm">
            <summary className="cursor-pointer text-primary">{t("showAll")}</summary>
            <ul className="mt-2 flex flex-col gap-1" dir="auto">
              {latest.answers.map((answer) => (
                <li key={answer.id} className="flex justify-between gap-4">
                  <span>{answer.question}</span>
                  <span className="shrink-0 font-medium">{answer.answer ? t("yes") : t("no")}</span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-muted" dir="auto">
              {latest.statement}
            </p>
          </details>
        </div>
      )}

      {reviewable && latest && (
        <form action={reviewDeclaration.bind(null, clientId, latest.id)} className="flex flex-col gap-3 border-t border-border pt-4">
          <p className="text-sm">{t("reviewHint")}</p>
          <label className="flex flex-col gap-1 text-sm">
            <span className="font-medium">{t("note")}</span>
            <input
              name="note"
              maxLength={2000}
              className="w-full min-w-0 control px-3 py-2"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button
              type="submit"
              name="decision"
              value="approve"
              className="btn-primary px-4 py-2 text-sm"
            >
              {t("approve")}
            </button>
            <button
              type="submit"
              name="decision"
              value="reject"
              className="btn-secondary px-4 py-2 text-sm text-danger"
            >
              {t("reject")}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
