import { TicketPercent } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { SummaryTiles } from "@/components/ui/summary-tiles";
import { unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { deletePromoCode, setPromoActive } from "./promos/actions";
import { catalogHref, type CatalogShow } from "./tabs";

/** Discount codes: tiles that filter, then a list. A row opens the code in a window; pause,
 * resume and delete are also one click away in the row. */
export async function CodesTab({ show }: { show: CatalogShow }) {
  const t = await getTranslations();
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("catalog.read");
  const all = unwrap(await api.GET("/promo-codes", { params: scope }));
  const codes = all.filter((code) => (show === "all" ? true : show === "active" ? code.active : !code.active));
  const writable = canWriteCatalog(tenant);
  const day = (value: string) => formatDay(value, locale, { day: "numeric", month: "short", year: "numeric" });
  const given = all.reduce((sum, code) => sum + code.discount_given, 0);
  const tile = (key: CatalogShow, value: number, hint?: string) => ({
    key,
    label: t(`catalog.tiles.codes.${key}`),
    value,
    hint,
    href: catalogHref("codes", key),
    active: show === key,
  });

  return (
    <>
      <SummaryTiles
        label={t("catalog.tiles.label")}
        tiles={[
          tile("all", all.length, given > 0 ? t("promo.given", { amount: formatMoney(given, tenant.currency, locale) }) : undefined),
          tile("active", all.filter((code) => code.active).length),
          tile("paused", all.filter((code) => !code.active).length),
        ]}
      />
      {codes.length === 0 ? (
        <EmptyState variant="list">
          <span className="flex max-w-md flex-col items-center gap-3">
            <span className="font-semibold text-foreground">{t("catalog.codesEmpty.title")}</span>
            <span>{t("catalog.codesEmpty.body")}</span>
            {all.length === 0 && writable && (
              <Link href="/catalog/promos/new" className="btn-primary px-4 py-2.5">
                {t("catalog.codesEmpty.cta")}
              </Link>
            )}
          </span>
        </EmptyState>
      ) : (
        <ul className="card flex flex-col divide-y divide-border">
          {codes.map((code) => (
            <li key={code.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
              <Link href={`/catalog/promos/${code.id}`} scroll={false} className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="flex items-center gap-2">
                  <TicketPercent aria-hidden="true" className="size-4 text-primary-ink" />
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
              </Link>
              {writable && (
                <span className="flex items-center gap-3 text-sm">
                  <form action={setPromoActive.bind(null, code.id, !code.active)}>
                    <button type="submit" className="btn-link text-primary-ink underline-offset-4 hover:underline">
                      {code.active ? t("promo.pause") : t("promo.resume")}
                    </button>
                  </form>
                  {code.uses === 0 && (
                    <form action={deletePromoCode.bind(null, code.id)}>
                      <button type="submit" className="btn-link text-danger underline-offset-4 hover:underline">
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
    </>
  );
}
