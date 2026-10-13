import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";
import { BRAND } from "@business-os/i18n/brand";

import { BackLink } from "@/components/back-link";
import { unwrap } from "@/lib/api";
import { canManageTeam } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { DecisionForm } from "./decision-form";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("timeOffQueue");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** Time-off requests waiting for a manager, then the recently decided ones. */
export default async function TimeOffRequestsPage() {
  const t = await getTranslations("timeOffQueue");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenant();
  if (!canManageTeam(tenant)) redirect("/dashboard");
  const requests = unwrap(await api.GET("/time-off-requests", { params: scope }));
  const pending = requests.filter((request) => request.status === "pending");
  const decided = requests.flatMap((request) => (request.status === "pending" ? [] : [{ ...request, status: request.status }]));
  // Requests carry plain calendar dates, so format them without any zone shift.
  const day = (iso: string) => new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: "UTC" }).format(new Date(`${iso}T00:00:00Z`));
  const period = (from: string, to: string) => (from === to ? day(from) : `${day(from)} – ${day(to)}`);

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/team/shifts" label={t("back")} />
      <PageHeader title={t("title")} description={t("subtitle")} />
      <section aria-labelledby="pending-heading" className="flex flex-col gap-3">
        <h2 id="pending-heading" className="text-lg font-semibold">
          {t("pending", { count: pending.length })}
        </h2>
        {pending.length === 0 && <p className="card p-5 text-sm text-muted">{t("noPending")}</p>}
        {pending.map((request) => (
          <article key={request.id} className="card flex flex-col gap-3 p-5">
            <div className="flex flex-col gap-1">
              <h3 dir="auto" className="font-medium">{request.user_name}</h3>
              <p className="text-sm">{period(request.starts_on, request.ends_on)}</p>
              {request.reason && <p dir="auto" className="text-sm text-muted">{request.reason}</p>}
              <p className={`text-sm ${request.shift_count > 0 ? "text-warning" : "text-muted"}`}>{t("shiftCount", { count: request.shift_count })}</p>
            </div>
            <DecisionForm requestId={request.id} />
          </article>
        ))}
      </section>
      {decided.length > 0 && (
        <section aria-labelledby="decided-heading" className="flex flex-col gap-3">
          <h2 id="decided-heading" className="text-lg font-semibold">
            {t("decided")}
          </h2>
          <ul className="card divide-y divide-border">
            {decided.map((request) => (
              <li key={request.id} className="flex flex-col gap-0.5 p-4 text-sm">
                <span className="font-medium">
                  {request.user_name} · {period(request.starts_on, request.ends_on)}
                </span>
                <span className="text-muted">
                  {t(`status.${request.status}`)}
                  {request.decided_by_name ? ` · ${request.decided_by_name}` : ""}
                  {request.decision_note ? ` · ${request.decision_note}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </Container>
  );
}
