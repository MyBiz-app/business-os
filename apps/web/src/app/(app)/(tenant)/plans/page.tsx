import { BadgeCheck, Ticket, TicketPercent, TrendingUp, Users } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { FormNotice } from "@/components/form/form-message";
import { unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { deletePromoCode, setPromoActive } from "./promo-actions";
import { PromoForm } from "./promo-form";

export default async function PlansPage({ searchParams }: PageProps<"/plans">) {
  const { removed } = await searchParams;
  const t = await getTranslations();
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("catalog.read");
  const [plans, codes] = await Promise.all([
    api.GET("/plans", { params: scope }).then(unwrap),
    api.GET("/promo-codes", { params: scope }).then(unwrap),
  ]);
  const writable = canWriteCatalog(tenant);
  const currencySymbol =
    new Intl.NumberFormat(locale, { style: "currency", currency: tenant.currency })
      .formatToParts(0)
      .find((part) => part.type === "currency")?.value ?? tenant.currency;
  const day = (value: string) => formatDay(value, locale, { day: "numeric", month: "short", year: "numeric" });

  return (
    <main className="enter mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-10">
      {(removed === "deleted" || removed === "archived") && <FormNotice message={t(`plans.removed.${removed}`)} />}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold">{t("plans.title")}</h1>
          <p className="text-sm text-muted">{t("plans.subtitle")}</p>
        </div>
        {canWriteCatalog(tenant) && (
          <Link href="/plans/new" className="btn-primary px-4 py-2.5">
            {t("plans.add")}
          </Link>
        )}
      </div>

      {plans.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border p-10 text-center text-muted">{t("plans.empty")}</p>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {plans.map((plan) => (
            <li key={plan.id}>
              <Link
                href={`/plans/${plan.id}`}
                className={`flex h-full flex-col gap-4 card card-hover p-5 ${plan.active ? "" : "opacity-60"}`}
              >
                <span className="flex items-start gap-3">
                  <span aria-hidden="true" className="inline-flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    {plan.kind === "membership" ? <BadgeCheck className="size-5" /> : <Ticket className="size-5" />}
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="font-semibold">{plan.name}</span>
                    <span className="text-sm text-muted">
                      {t(`plans.kinds.${plan.kind}`)} ·{" "}
                      {plan.credits ? `${t("plans.creditsCount", { count: plan.credits })} · ` : ""}
                      {t("plans.days", { count: plan.validity_days })}
                      {!plan.active && ` · ${t("common.inactive")}`}
                    </span>
                  </span>
                  <span className="text-xl font-bold tabular-nums" dir="ltr">
                    {formatMoney(plan.price_amount, plan.price_currency, locale)}
                  </span>
                </span>
                <span className="mt-auto flex flex-wrap gap-x-4 gap-y-1 border-t border-border pt-3 text-sm text-muted">
                  <span className="inline-flex items-center gap-1.5">
                    <Users aria-hidden="true" className="size-4" />
                    {t("plans.stats.holders", { count: plan.holders })}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <TrendingUp aria-hidden="true" className="size-4" />
                    {t("plans.stats.sold", { count: plan.sold_last_30_days })}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      <section aria-labelledby="promo-heading" className="card flex flex-col gap-4 p-6">
        <div className="flex flex-col gap-1">
          <h2 id="promo-heading" className="flex items-center gap-2 text-lg font-semibold">
            <TicketPercent aria-hidden="true" className="size-5 text-primary" />
            {t("promo.title")}
          </h2>
          <p className="text-sm text-muted">{t("promo.subtitle")}</p>
        </div>
        {codes.length > 0 && (
          <ul className="flex flex-col divide-y divide-border">
            {codes.map((code) => (
              <li key={code.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <span className="flex min-w-0 flex-col gap-0.5">
                  <span className="flex items-center gap-2">
                    <span dir="ltr" className="rounded-lg bg-primary/10 px-2 py-0.5 font-mono font-bold tracking-wider">
                      {code.code}
                    </span>
                    <span className="font-semibold">
                      {code.percent_off
                        ? t("promo.percentOff", { value: code.percent_off })
                        : t("promo.amountOff", { value: formatMoney(code.amount_off ?? 0, tenant.currency, locale) })}
                    </span>
                    {!code.active && <span className="text-xs text-muted">· {t("promo.paused")}</span>}
                  </span>
                  <span className="text-xs text-muted">
                    {code.plan_name ?? t("promo.allPlans")}
                    {code.ends_on && ` · ${t("promo.until", { date: day(code.ends_on) })}`}
                    {" · "}
                    {code.max_uses ? t("promo.usesOf", { uses: code.uses, max: code.max_uses }) : t("promo.uses", { uses: code.uses })}
                    {code.discount_given > 0 && ` · ${t("promo.given", { amount: formatMoney(code.discount_given, tenant.currency, locale) })}`}
                  </span>
                </span>
                {writable && (
                  <span className="flex items-center gap-3 text-sm">
                    <form action={setPromoActive.bind(null, code.id, !code.active)}>
                      <button type="submit" className="text-primary underline-offset-4 hover:underline">
                        {code.active ? t("promo.pause") : t("promo.resume")}
                      </button>
                    </form>
                    {code.uses === 0 && (
                      <form action={deletePromoCode.bind(null, code.id)}>
                        <button type="submit" className="text-danger underline-offset-4 hover:underline">
                          {t("promo.delete")}
                        </button>
                      </form>
                    )}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
        {writable && (
          <div className="border-t border-border pt-4">
            <PromoForm plans={plans.filter((p) => p.active).map((p) => ({ id: p.id, name: p.name }))} currencySymbol={currencySymbol} />
          </div>
        )}
      </section>
    </main>
  );
}
