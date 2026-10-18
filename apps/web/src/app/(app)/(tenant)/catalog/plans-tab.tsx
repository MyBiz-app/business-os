import { BadgeCheck, Ticket, TrendingUp, Users } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { SummaryTiles } from "@/components/ui/summary-tiles";
import { unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { catalogHref, type CatalogShow } from "./tabs";

/** Memberships and punch cards: tiles that filter, then the cards. Each card opens in a window. */
export async function PlansTab({ show }: { show: CatalogShow }) {
  const t = await getTranslations();
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("catalog.read");
  const all = unwrap(await api.GET("/plans", { params: scope }));
  const plans = all.filter((plan) => (show === "all" ? true : show === "active" ? plan.active : !plan.active));
  const tile = (key: CatalogShow, value: number, hint?: string) => ({
    key,
    label: t(`catalog.tiles.plans.${key}`),
    value,
    hint,
    href: catalogHref("plans", key),
    active: show === key,
  });

  return (
    <>
      <SummaryTiles
        label={t("catalog.tiles.label")}
        tiles={[
          tile("all", all.length, t("catalog.soldLast30", { count: all.reduce((sum, plan) => sum + plan.sold_last_30_days, 0) })),
          tile("active", all.filter((plan) => plan.active).length),
          tile("paused", all.filter((plan) => !plan.active).length),
        ]}
      />
      {plans.length === 0 ? (
        <EmptyState variant="list">
          <span className="flex max-w-md flex-col items-center gap-3">
            <span className="font-semibold text-foreground">{t("catalog.plansEmpty.title")}</span>
            <span>{t("catalog.plansEmpty.body")}</span>
            {all.length === 0 && canWriteCatalog(tenant) && (
              <Link href="/catalog/plans/new" className="btn-primary px-4 py-2.5">
                {t("catalog.plansEmpty.cta")}
              </Link>
            )}
          </span>
        </EmptyState>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {plans.map((plan) => (
            <li key={plan.id}>
              <Link
                href={`/catalog/plans/${plan.id}`}
                scroll={false}
                className={`flex h-full flex-col gap-4 card card-hover p-5 ${plan.active ? "" : "opacity-60"}`}
              >
                <span className="flex items-start gap-3">
                  <span aria-hidden="true" className="inline-flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary-ink">
                    {plan.kind === "membership" ? <BadgeCheck className="size-5" /> : <Ticket className="size-5" />}
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span dir="auto" className="font-semibold">{plan.name}</span>
                    <span className="text-sm text-muted">
                      {t(`plans.kinds.${plan.kind}`)} ·{" "}
                      {plan.credits ? `${t("plans.creditsCount", { count: plan.credits })} · ` : ""}
                      {plan.billing_cycle
                        ? `${t(`plans.cycles.${plan.billing_cycle}`)}${plan.auto_renew ? ` · ${t("plans.autoRenew")}` : ""}`
                        : t("plans.days", { count: plan.validity_days })}
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
    </>
  );
}
