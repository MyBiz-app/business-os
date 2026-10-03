import { getLocale, getTranslations } from "next-intl/server";

import { todayIn } from "@/lib/dates";
import { unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { canSell } from "@/lib/permissions";
import type { getTenant } from "@/lib/tenant";

import { cancelEntitlement, freezeEntitlement, sellPlan } from "./plan-actions";
import { FreezeForm, SellPlanForm } from "./plan-forms";

const TONE = {
  active: "bg-success/15 text-success",
  upcoming: "bg-primary/15 text-primary",
  frozen: "bg-primary/15 text-primary",
  used_up: "bg-border text-muted",
  expired: "bg-border text-muted",
  cancelled: "bg-border text-muted",
} as const;

/** A fresh key per rendered form: resubmitting the same form can never sell twice. */
function newSaleKey(): string {
  return `sale-${crypto.randomUUID()}`;
}

type Props = { clientId: string; context: Awaited<ReturnType<typeof getTenant>> };

/** The client's plans (entitlements): sell, freeze, cancel. Payment is simulated for now. */
export async function PlansSection({ clientId, context }: Props) {
  const t = await getTranslations("plans");
  const locale = await getLocale();
  const { tenant, api, scope } = context;
  const [entitlements, plans] = await Promise.all([
    api.GET("/clients/{client_id}/entitlements", { params: { ...scope, path: { client_id: clientId } } }).then(unwrap),
    api.GET("/plans", { params: { ...scope, query: { active: true } } }).then(unwrap),
  ]);
  const selling = canSell(tenant.role);
  const today = todayIn(tenant.time_zone);
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: "UTC" });
  const formatDate = (day: string) => date.format(new Date(`${day}T12:00:00Z`));

  return (
    <section aria-labelledby="plans-heading" className="flex flex-col gap-4 rounded-2xl border border-border bg-surface p-6">
      <h2 id="plans-heading" className="text-lg font-semibold">
        {t("clientPlans")}
      </h2>

      {entitlements.length === 0 ? (
        <p className="text-sm text-muted">{t("noPlans")}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-border">
          {entitlements.map((entitlement) => {
            const open = entitlement.state !== "cancelled" && entitlement.state !== "expired";
            return (
              <li key={entitlement.id} className="flex flex-col gap-1 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="flex items-center gap-2">
                    <span className="font-semibold">{entitlement.name}</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${TONE[entitlement.state]}`}>
                      {t(`states.${entitlement.state}`)}
                    </span>
                  </span>
                  <span className="text-sm" dir="ltr">
                    {formatMoney(entitlement.price_amount, entitlement.price_currency, locale)}
                  </span>
                </div>
                <p className="text-sm text-muted">
                  {t("validityRange", { from: formatDate(entitlement.starts_on), to: formatDate(entitlement.ends_on) })}
                  {" · "}
                  {entitlement.credits === null
                    ? t("unlimitedUsed", { used: entitlement.credits_used })
                    : t("creditsLeft", { left: entitlement.credits_remaining ?? 0, total: entitlement.credits })}
                </p>
                {entitlement.freezes.map((freeze) => (
                  <p key={freeze.id} className="text-sm text-muted">
                    {t("frozenRange", { from: formatDate(freeze.starts_on), to: formatDate(freeze.ends_on) })}
                    {freeze.reason && ` · ${freeze.reason}`}
                  </p>
                ))}
                {selling && open && (
                  <div className="flex flex-wrap items-start gap-4">
                    <details className="flex-1">
                      <summary className="cursor-pointer text-sm text-primary">{t("freeze")}</summary>
                      <FreezeForm action={freezeEntitlement.bind(null, clientId, entitlement.id)} today={today} />
                    </details>
                    <form action={cancelEntitlement.bind(null, clientId, entitlement.id)}>
                      <button type="submit" className="text-sm text-danger underline-offset-4 hover:underline">
                        {t("cancelPlan")}
                      </button>
                    </form>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {selling && plans.length > 0 && (
        <div className="flex flex-col gap-3 border-t border-border pt-4">
          <h3 className="font-semibold">{t("sellTitle")}</h3>
          <SellPlanForm
            action={sellPlan.bind(null, clientId)}
            plans={plans.map((plan) => ({
              value: plan.id,
              label: `${plan.name} · ${formatMoney(plan.price_amount, plan.price_currency, locale)}`,
            }))}
            today={today}
            idempotencyKey={newSaleKey()}
          />
        </div>
      )}
    </section>
  );
}
