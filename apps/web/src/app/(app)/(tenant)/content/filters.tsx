import { getTranslations } from "next-intl/server";

import { NetworkIcon } from "./network-icon";

export type Range = "7" | "30" | "90" | "custom";

/** Which networks, which period, and whether to compare: a plain form, so it works without
 * scripts and the chosen view stays in the address (shareable, printable). */
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
  const ranges: Range[] = ["7", "30", "90", "custom"];
  return (
    <form method="get" aria-label={t("filters.label")} className="card flex flex-col gap-4 p-5 print:hidden">
      <input type="hidden" name="sort" value={sort} />
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-sm font-semibold">{t("filters.networks")}</legend>
        <div className="flex flex-wrap gap-2">
          {networks.map((network) => (
            <label key={network} className="has-[:checked]:bg-primary/10 has-[:checked]:ring-primary flex cursor-pointer items-center gap-2 rounded-full bg-surface py-1 ps-1.5 pe-3 text-sm font-medium ring-1 ring-border has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary">
              <input type="checkbox" name="network" value={network} defaultChecked={chosen.includes(network)} className="sr-only" />
              <NetworkIcon network={network} size="sm" />
              {t(`networks.${network}` as "networks.facebook")}
            </label>
          ))}
        </div>
        <p className="text-xs text-muted">{t("filters.allNetworks")}</p>
      </fieldset>
      <div className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-semibold">{t("filters.period")}</legend>
          <div className="flex flex-wrap gap-2">
            {ranges.map((value) => (
              <label key={value} className="has-[:checked]:bg-primary has-[:checked]:text-white cursor-pointer rounded-full bg-surface px-3 py-1 text-sm font-medium ring-1 ring-border has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary">
                <input type="radio" name="range" value={value} defaultChecked={range === value} className="sr-only" />
                {t(`filters.${value === "custom" ? "custom" : `d${value}`}` as "filters.d7")}
              </label>
            ))}
          </div>
        </fieldset>
        <label className="flex flex-col gap-1 text-sm font-medium">
          {t("filters.from")}
          <input type="date" name="from" defaultValue={from} className="control px-3 py-1.5" />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          {t("filters.to")}
          <input type="date" name="to" defaultValue={to} className="control px-3 py-1.5" />
        </label>
        <label className="flex items-center gap-2 pb-2 text-sm font-medium">
          <input type="checkbox" name="compare" value="1" defaultChecked={compare} className="size-4 accent-[var(--color-primary)]" />
          {t("filters.compare")}
        </label>
        <button type="submit" className="btn-primary px-5 py-2">
          {t("filters.apply")}
        </button>
      </div>
    </form>
  );
}
