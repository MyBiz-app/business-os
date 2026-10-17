import { getLocale, getTranslations } from "next-intl/server";
import { notFound, redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { canWriteCatalog } from "@/lib/permissions";
import { getTenantFor } from "@/lib/tenant";

import { CatalogPage } from "../page-shell";
import { PromoActions } from "./promo-actions-bar";
import { PromoForm } from "./promo-form";
import { PromoDialog } from "./promo-dialog";
import { removePromoCode, setPromoActive } from "./actions";

const BACK = "/catalog?tab=codes";

/** A new discount code. `modal`: a window over the list; otherwise a page (the shared link). */
export async function NewPromo({ modal }: { modal: boolean }) {
  const t = await getTranslations("promo");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("catalog.read");
  if (!canWriteCatalog(tenant)) redirect(BACK);
  const plans = unwrap(await api.GET("/plans", { params: scope }));
  const currencySymbol =
    new Intl.NumberFormat(locale, { style: "currency", currency: tenant.currency })
      .formatToParts(0)
      .find((part) => part.type === "currency")?.value ?? tenant.currency;
  const form = <PromoForm modal={modal} plans={plans.filter((p) => p.active).map((p) => ({ id: p.id, name: p.name }))} currencySymbol={currencySymbol} />;
  return modal ? form : <CatalogPage title={t("new")} backHref={BACK}>{form}</CatalogPage>;
}

/** One code: what it gives, where it applies and how it was used, with pause / resume / delete. */
export async function PromoEditor({ id, modal }: { id: string; modal: boolean }) {
  const t = await getTranslations("promo");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenantFor("catalog.read");
  const codes = unwrap(await api.GET("/promo-codes", { params: scope }));
  const code = codes.find((c) => c.id === id);
  if (!code) notFound();
  const day = (value: string) => formatDay(value, locale, { day: "numeric", month: "short", year: "numeric" });
  const rows: [string, string][] = [
    [t("kind"), code.percent_off ? t("percentOff", { value: code.percent_off }) : t("amountOff", { value: formatMoney(code.amount_off ?? 0, tenant.currency, locale) })],
    [t("plan"), code.plan_name ?? t("allPlans")],
    [t("startsOn"), code.starts_on ? day(code.starts_on) : "-"],
    [t("endsOn"), code.ends_on ? day(code.ends_on) : "-"],
    [t("usesLabel"), code.max_uses ? t("usesOf", { uses: code.uses, max: code.max_uses }) : t("uses", { uses: code.uses })],
    [t("givenLabel"), formatMoney(code.discount_given, tenant.currency, locale)],
  ];
  const writable = canWriteCatalog(tenant);
  const body = (
    <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
      {rows.map(([label, value]) => (
        <div key={label} className="flex flex-col gap-0.5">
          <dt className="text-sm text-muted">{label}</dt>
          <dd className="font-medium">{value}</dd>
        </div>
      ))}
      <div className="flex flex-col gap-0.5">
        <dt className="text-sm text-muted">{t("statusLabel")}</dt>
        <dd className="font-medium">{code.active ? t("activeNow") : t("paused")}</dd>
      </div>
    </dl>
  );
  const actions = writable ? (
    <PromoActions
      active={code.active}
      deletable={code.uses === 0}
      toggle={setPromoActive.bind(null, code.id, !code.active)}
      remove={removePromoCode.bind(null, code.id)}
      toggleLabel={code.active ? t("pause") : t("resume")}
      deleteLabel={t("delete")}
      deleteConfirm={t("deleteConfirm", { code: code.code })}
    />
  ) : null;
  const title = <span dir="ltr" className="font-mono">{code.code}</span>;
  if (modal) return <PromoDialog code={code.code} actions={actions}>{body}</PromoDialog>;
  return (
    <CatalogPage title={title} backHref={BACK}>
      <div className="card flex flex-col gap-5 p-6">
        {body}
        {actions}
      </div>
    </CatalogPage>
  );
}
