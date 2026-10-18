import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { Pill, type Tone } from "@/components/pill";
import { todayIn } from "@/lib/dates";
import { unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { canSell } from "@/lib/permissions";
import type { getTenant } from "@/lib/tenant";

import {
  approveFreezeRequest,
  cancelEntitlement,
  endFreezeEarly,
  freezeEntitlement,
  rejectFreezeRequest,
  sellPlan,
} from "./plan-actions";
import { EndFreezeButton, FreezeForm, RequestDecision, SellPlanForm } from "./plan-forms";

const TONE: Record<string, Tone> = {
  active: "success",
  upcoming: "primary",
  frozen: "primary",
  used_up: "muted",
  expired: "muted",
  cancelled: "muted",
};

/** A fresh key per rendered form: resubmitting the same form can never sell twice. */
function newSaleKey(): string {
  return `sale-${crypto.randomUUID()}`;
}

type Props = {
  clientId: string;
  context: Awaited<ReturnType<typeof getTenant>>;
  /** History only (an erased client): no new sales, freezes or cancellations. */
  locked?: boolean;
};

/** The client's plans (entitlements): sell, freeze, cancel. Payment is simulated for now. */
export async function PlansSection({ clientId, context, locked = false }: Props) {
  const t = await getTranslations("plans");
  const tReceipts = await getTranslations("receipts");
  const tFreeze = await getTranslations("freeze");
  const locale = await getLocale();
  const { tenant, api, scope } = context;
  const selling = canSell(tenant) && !locked;
  const [entitlements, plans, requests] = await Promise.all([
    api.GET("/clients/{client_id}/entitlements", { params: { ...scope, path: { client_id: clientId } } }).then(unwrap),
    tenant.permissions.includes("catalog.read")
      ? api.GET("/plans", { params: { ...scope, query: { active: true } } }).then(unwrap)
      : Promise.resolve([]),
    canSell(tenant)
      ? api
          .GET("/freeze-requests", { params: { ...scope, query: { status: "pending", client_id: clientId } } })
          .then(unwrap)
      : Promise.resolve([]),
  ]);
  const today = todayIn(tenant.time_zone);
  const date = new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: "UTC" });
  const reasons: readonly string[] = ["travel", "reserve_duty", "illness", "pregnancy", "other"];
  /** A freeze made by a client names one of the app's reasons; a manager's is free text. */
  const reasonLabel = (reason: string) =>
    reasons.includes(reason) ? tFreeze(`reasons.${reason as "travel" | "reserve_duty" | "illness" | "pregnancy" | "other"}`) : reason;
  const formatDate = (day: string) => date.format(new Date(`${day}T12:00:00Z`));

  return (
    <section aria-labelledby="plans-heading" className="flex flex-col gap-4 card p-6">
      <h2 id="plans-heading" className="text-lg font-semibold">
        {t("clientPlans")}
      </h2>

      {selling && requests.length > 0 && (
        <div className="flex flex-col gap-2 rounded-xl bg-primary/5 p-4">
          <h3 className="font-semibold">{t("requestsTitle")}</h3>
          <ul className="flex flex-col divide-y divide-border">
            {requests.map((request) => (
              <li key={request.id} className="flex flex-col gap-1 py-2">
                <p className="text-sm font-medium">{request.entitlement_name}</p>
                <p className="text-sm text-muted">
                  {t("requestLine", {
                    from: formatDate(request.starts_on),
                    to: formatDate(request.ends_on),
                    days: request.days,
                    reason: reasonLabel(request.reason),
                  })}
                  {request.note && ` · ${request.note}`}
                </p>
                <RequestDecision
                  request={request}
                  approve={approveFreezeRequest.bind(null, clientId, request.id)}
                  reject={rejectFreezeRequest.bind(null, clientId, request.id)}
                />
              </li>
            ))}
          </ul>
        </div>
      )}

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
                    <Pill tone={TONE[entitlement.state]}>{t(`states.${entitlement.state}`)}</Pill>
                  </span>
                  <span className="flex items-center gap-3 text-sm">
                    {entitlement.receipt_id && (
                      <Link href={`/receipts/${entitlement.receipt_id}`} className="text-primary-ink underline-offset-4 hover:underline">
                        {tReceipts("short", { number: entitlement.receipt_number ?? "" })}
                      </Link>
                    )}
                    <span dir="ltr">{formatMoney(entitlement.price_amount, entitlement.price_currency, locale)}</span>
                  </span>
                </div>
                <p className="text-sm text-muted">
                  {t("validityRange", { from: formatDate(entitlement.starts_on), to: formatDate(entitlement.ends_on) })}
                  {" · "}
                  {entitlement.credits === null
                    ? t("unlimitedUsed", { used: entitlement.credits_used })
                    : t("creditsLeft", { left: entitlement.credits_remaining ?? 0, total: entitlement.credits })}
                </p>
                {entitlement.next_billing_on && (
                  <p className="text-sm text-muted">
                    {t(entitlement.auto_renew ? "renews" : "renewsOff", {
                      date: formatDate(entitlement.next_billing_on),
                      amount: formatMoney(entitlement.next_billing_amount ?? entitlement.price_amount, entitlement.price_currency, locale),
                    })}
                  </p>
                )}
                {entitlement.freezes.map((freeze) => (
                  <div key={freeze.id} className="flex flex-col gap-0.5">
                    <p className="text-sm text-muted">
                      {t("frozenRange", { from: formatDate(freeze.starts_on), to: formatDate(freeze.ends_on) })}
                      {freeze.reason && ` · ${reasonLabel(freeze.reason)}`}
                      {freeze.request_id && ` · ${t("requestsRequestedBy")}`}
                    </p>
                    {(freeze.billing_shift_days > 0 || freeze.credit_amount > 0 || freeze.fee_amount > 0) && (
                      <p className="text-xs text-muted">
                        {[
                          freeze.billing_shift_days > 0 && t("freezeShifted", { days: freeze.billing_shift_days }),
                          freeze.credit_amount > 0 && t("freezeCredit", { amount: formatMoney(freeze.credit_amount, entitlement.price_currency, locale) }),
                          freeze.fee_amount > 0 && t("freezeFee", { amount: formatMoney(freeze.fee_amount, entitlement.price_currency, locale) }),
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    )}
                    {selling && freeze.ends_on >= today && (
                      <EndFreezeButton action={endFreezeEarly.bind(null, clientId, freeze.id)} />
                    )}
                  </div>
                ))}
                {selling && open && (
                  <div className="flex flex-wrap items-start gap-4">
                    {entitlement.freezable ? (
                      <details className="flex-1">
                        <summary className="cursor-pointer text-sm text-primary-ink">{t("freeze")}</summary>
                        <FreezeForm action={freezeEntitlement.bind(null, clientId, entitlement.id)} today={today} />
                      </details>
                    ) : (
                      <span className="flex-1 text-sm text-muted">{entitlement.kind === "punch_card" ? t("punchNoFreeze") : ""}</span>
                    )}
                    <form action={cancelEntitlement.bind(null, clientId, entitlement.id)}>
                      <button type="submit" className="btn-link text-sm text-danger underline-offset-4 hover:underline">
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
