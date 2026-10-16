import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";
import { BRAND } from "@business-os/i18n/brand";
import { dayOf, formatDay, formatTime } from "@business-os/i18n/dates";

import { BackLink } from "@/components/back-link";
import { unwrap } from "@/lib/api";
import { canManageTeam } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { DecisionForm } from "./decision-form";
import { isolate } from "@/lib/bidi";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("shiftSwapQueue");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** Shift swaps a colleague has accepted and a manager must decide, then the other recent ones. */
export default async function ShiftSwapsPage() {
  const t = await getTranslations("shiftSwapQueue");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenant();
  if (!canManageTeam(tenant)) redirect("/dashboard");
  const swaps = unwrap(await api.GET("/shift-swaps", { params: scope }));
  const waiting = swaps.filter((swap) => swap.status === "pending_manager");
  const others = swaps.filter((swap) => swap.status !== "pending_manager");
  const when = (swap: (typeof swaps)[number]) =>
    `${formatDay(dayOf(swap.starts_at, tenant.time_zone), locale, { weekday: "short", day: "numeric", month: "short" })} ` +
    `${formatTime(swap.starts_at, locale, tenant.time_zone)}-${formatTime(swap.ends_at, locale, tenant.time_zone)} · ${swap.location_name}`;

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/team/shifts" label={t("back")} />
      <PageHeader title={t("title")} description={t("subtitle")} />
      <section aria-labelledby="pending-heading" className="flex flex-col gap-3">
        <h2 id="pending-heading" className="text-lg font-semibold">
          {t("pending", { count: waiting.length })}
        </h2>
        {waiting.length === 0 && <p className="card p-5 text-sm text-muted">{t("noPending")}</p>}
        {waiting.map((swap) => (
          <article key={swap.id} className="card flex flex-col gap-3 p-5">
            <div className="flex flex-col gap-1">
              <h3 className="font-medium">{t("fromTo", { from: isolate(swap.from_user_name), to: isolate(swap.to_user_name) })}</h3>
              <p className="text-sm">{when(swap)}</p>
              {swap.note && <p dir="auto" className="text-sm text-muted">{swap.note}</p>}
            </div>
            <DecisionForm swapId={swap.id} />
          </article>
        ))}
      </section>
      {others.length > 0 && (
        <section aria-labelledby="decided-heading" className="flex flex-col gap-3">
          <h2 id="decided-heading" className="text-lg font-semibold">
            {t("decided")}
          </h2>
          <ul className="card divide-y divide-border">
            {others.map((swap) => (
              <li key={swap.id} className="flex flex-col gap-0.5 p-4 text-sm">
                <span className="font-medium">
                  {t("fromTo", { from: swap.from_user_name, to: swap.to_user_name })} · {when(swap)}
                </span>
                <span className="text-muted">
                  {t(`status.${swap.status}`)}
                  {swap.decided_by_name ? ` · ${swap.decided_by_name}` : ""}
                  {swap.decision_note ? ` · ${swap.decision_note}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </Container>
  );
}
