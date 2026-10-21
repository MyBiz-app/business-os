import { DataTable } from "@/components/ui/data-table";
import type { Metadata } from "next";
import { BRAND } from "@business-os/i18n/brand";
import { getLocale, getTranslations } from "next-intl/server";

import { EmptyState } from "@/components/empty-state";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { getPlatform } from "@/lib/platform";
import { industryTexts } from "@/lib/verticals";

const CURRENCIES = ["ILS", "USD", "EUR"] as const;

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("platform.catalog");
  return { title: `${t("title")} · ${BRAND.name}` };
}

/** The catalog and price list (K5), read-only: industries and how many people asked for the ones
 * not open yet, the core price tiers and every module with its prices. The prices live in code. */
export default async function PlatformCatalogPage() {
  const t = await getTranslations("platform.catalog");
  const tRoot = await getTranslations();
  const { text } = industryTexts(tRoot);
  const locale = await getLocale();
  const { api } = await getPlatform();
  const catalog = unwrap(await api.GET("/platform/catalog"));
  const number = new Intl.NumberFormat(locale);
  const categories = catalog.industries.filter((i) => i.parent === null);
  const kids = (parent: string) => catalog.industries.filter((i) => i.parent === parent);
  const showRequests = catalog.industries.some((i) => i.requests !== null);
  const money = (prices: Record<string, number>, currency: string, suffix = "") =>
    `${formatMoney(prices[currency] ?? 0, currency, locale)}${suffix}`;

  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-8 py-8 sm:py-10">
      <PageHeader title={t("title")} description={t("hint")} />

      <section aria-labelledby="catalog-industries" className="flex flex-col gap-4">
        <h2 id="catalog-industries" className="text-lg font-semibold">{t("industries")}</h2>
        {categories.length === 0 ? (
          <EmptyState variant="list">{t("empty")}</EmptyState>
        ) : (
          <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {categories.map((category) => (
              <li key={category.key} className="card flex flex-col gap-3 p-4 sm:p-5">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold">{text(category.key, "name")}</span>
                  <StatusBadge status={category.status} label={t(`status.${category.status}`)} />
                </div>
                <ul className="flex flex-col gap-2 text-sm">
                  {kids(category.key).map((kind) => (
                    <li key={kind.key} className="flex items-center justify-between gap-3">
                      <span>{text(kind.key, "name")}</span>
                      <span className="flex items-center gap-2">
                        {showRequests && kind.status === "planned" && (
                          <span className="text-xs text-muted" title={t("requestsHint")}>
                            {t("requests", { count: kind.requests ?? 0 })}
                          </span>
                        )}
                        <StatusBadge status={kind.status} label={t(`status.${kind.status}`)} />
                      </span>
                    </li>
                  ))}
                </ul>
                {showRequests && category.status === "planned" && (
                  <p className="text-xs text-muted">{t("requests", { count: category.requests ?? 0 })}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="catalog-core" className="flex flex-col gap-4">
        <h2 id="catalog-core" className="text-lg font-semibold">{t("core")}</h2>
        <DataTable
          labelledBy="catalog-core"
          rows={catalog.core}
          rowKey={(_, index) => index}
          columns={[
            {
              key: "tier",
              header: t("tier"),
              rowHeader: true,
              cell: (tier) => {
                const index = catalog.core.indexOf(tier);
                return tier.up_to_clients === null
                  ? t("tierOver", { count: number.format(catalog.core[index - 1]?.up_to_clients ?? 0) })
                  : t("tierUpTo", { count: number.format(tier.up_to_clients) });
              },
            },
            ...CURRENCIES.map((c) => ({
              key: c,
              header: c,
              align: "end" as const,
              className: "tabular-nums",
              cell: (tier: (typeof catalog.core)[number]) => <bdi dir="ltr">{money(tier.prices, c)}</bdi>,
            })),
          ]}
        />
      </section>

      <section aria-labelledby="catalog-modules" className="flex flex-col gap-4">
        <h2 id="catalog-modules" className="text-lg font-semibold">{t("modules")}</h2>
        <p className="text-sm text-muted">{t("placeholder")}</p>
        <DataTable
          labelledBy="catalog-modules"
          rows={catalog.modules}
          rowKey={(module) => module.key}
          columns={[
            { key: "module", header: t("module"), rowHeader: true, cell: (module) => tRoot(`modules.names.${module.key as "client_app"}`) },
            ...CURRENCIES.map((c) => ({
              key: c,
              header: c,
              align: "end" as const,
              className: "tabular-nums",
              cell: (module: (typeof catalog.modules)[number]) => <bdi dir="ltr">{money(module.prices, c)}</bdi>,
            })),
            {
              key: "notes",
              header: t("notes"),
              className: "text-xs text-muted",
              cell: (module) => {
                const name = (key: string) => tRoot(`modules.names.${key as "client_app"}`);
                const needs = [
                  ...module.requires_all.map(name),
                  ...(module.requires_any.length ? [module.requires_any.map(name).join(` ${t("or")} `)] : []),
                ];
                return [
                  module.billing === "once" ? t("once") : null,
                  module.per_unit ? t("perUnit") : null,
                  module.group ? t("oneOf", { group: module.group }) : null,
                  !module.available ? t("soon") : null,
                  module.ai_credits_included ? t("credits", { count: number.format(module.ai_credits_included) }) : null,
                  module.ai_users_included ? t("users", { count: module.ai_users_included }) : null,
                  needs.length ? t("needs", { list: needs.join(", ") }) : null,
                ]
                  .filter(Boolean)
                  .join(" · ");
              },
            },
          ]}
        />
      </section>
    </Container>
  );
}

function StatusBadge({ status, label }: { status: "live" | "beta" | "planned"; label: string }) {
  const tone = status === "live" ? "bg-success/15 text-success" : status === "beta" ? "bg-primary/10 text-primary" : "bg-warning/20";
  return <span className={`rounded-full px-2.5 py-0.5 text-xs ${tone}`}>{label}</span>;
}
