import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { canWriteCatalog } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

export default async function PlansPage() {
  const t = await getTranslations();
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenant();
  const plans = unwrap(await api.GET("/plans", { params: scope }));

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl font-bold">{t("plans.title")}</h1>
          <p className="text-sm text-muted">{t("plans.subtitle")}</p>
        </div>
        {canWriteCatalog(tenant.role) && (
          <Link href="/plans/new" className="rounded-lg bg-primary px-4 py-2.5 font-semibold text-on-primary">
            {t("plans.add")}
          </Link>
        )}
      </div>

      {plans.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-border p-10 text-center text-muted">{t("plans.empty")}</p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {plans.map((plan) => (
            <li key={plan.id}>
              <Link
                href={`/plans/${plan.id}`}
                className={`flex flex-col gap-1 rounded-2xl border border-border bg-surface p-4 hover:border-primary ${plan.active ? "" : "opacity-60"}`}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="font-semibold">{plan.name}</span>
                  <span className="text-sm font-medium" dir="ltr">
                    {formatMoney(plan.price_amount, plan.price_currency, locale)}
                  </span>
                </span>
                <span className="text-sm text-muted">
                  {t(`plans.kinds.${plan.kind}`)} ·{" "}
                  {plan.credits ? `${t("plans.creditsCount", { count: plan.credits })} · ` : ""}
                  {t("plans.days", { count: plan.validity_days })}
                  {!plan.active && ` · ${t("common.inactive")}`}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
