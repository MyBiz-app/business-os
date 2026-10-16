import { getTranslations } from "next-intl/server";

import { FilterBar } from "./filter-bar";

export type Range = "7" | "30" | "90" | "month" | "last_month" | "custom";

/** Which networks, which period, and whether to compare. The bar applies a change at once and
 * keeps the view in the address (shareable, printable). */
export async function Filters({
  networks,
  chosen,
  range,
  from,
  to,
  compare,
  sort,
}: {
  networks: string[];
  chosen: string[];
  range: Range;
  from: string;
  to: string;
  compare: boolean;
  sort: string;
}) {
  const t = await getTranslations("content");
  return (
    <FilterBar
      networks={networks.map((value) => ({ value, label: t(`networks.${value}` as "networks.facebook") }))}
      chosen={chosen}
      range={range}
      from={from}
      to={to}
      compare={compare}
      sort={sort}
      labels={{
        bar: t("filters.label"),
        networks: t("filters.networks"),
        allNetworks: t("filters.allNetworks"),
        selectAll: t("filters.selectAll"),
        period: t("filters.period"),
        compare: t("filters.compare"),
        compareShort: t("filters.compareShort"),
        from: t("filters.from"),
        to: t("filters.to"),
        reset: t("filters.reset"),
        filtersButton: t("filters.filtersButton"),
        remove: t("filters.remove"),
        ranges: {
          "7": t("filters.d7"),
          "30": t("filters.d30"),
          "90": t("filters.d90"),
          month: t("filters.month"),
          last_month: t("filters.lastMonth"),
          custom: t("filters.custom"),
        },
      }}
    />
  );
}
