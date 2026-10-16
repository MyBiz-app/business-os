import { Coins } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";

import { SubmitButton } from "@/components/form/submit-button";
import { formatMoney } from "@/lib/money";
import type { components } from "@business-os/api-client";

import { saveAiSpend } from "./actions";

type Spend = components["schemas"]["AiSpend"];

/** Pay-as-you-go extra AI credits: off by default, with an optional monthly cap. */
export async function AiSpend({ spend }: { spend: Spend }) {
  const t = await getTranslations("billing.aiSpend");
  const locale = await getLocale();
  const money = (amount: number) => formatMoney(amount, spend.currency, locale);
  const alert = Math.max(0, ...spend.alerts);

  return (
    <section aria-labelledby="ai-spend-heading" className="card flex flex-col gap-4 p-6">
      <h2 id="ai-spend-heading" className="flex items-center gap-2 text-lg font-semibold">
        <Coins aria-hidden="true" className="size-5 text-primary" />
        {t("title")}
      </h2>
      <p className="text-sm text-muted">
        {t("intro", { included: spend.credits_included, price: money(spend.price_per_100_minor) })}
      </p>
      {alert >= 80 && (
        <p role="status" className="rounded-xl border border-warning/50 bg-warning/10 px-4 py-2 text-sm">
          {t("alerts", { percent: alert })}
        </p>
      )}
      {spend.credits_included === 0 ? (
        <p className="text-sm">{t("needModule")}</p>
      ) : (
        <form action={saveAiSpend} className="flex flex-col gap-4">
          <label className="flex items-center gap-3 text-sm font-medium">
            <input type="checkbox" name="payg" defaultChecked={spend.payg_enabled} className="size-4" />
            {t("toggle")}
          </label>
          <label className="flex max-w-xs flex-col gap-1 text-sm font-medium">
            {t("cap", { currency: spend.currency })}
            <input
              type="number"
              name="cap"
              min={0}
              step={1}
              inputMode="numeric"
              defaultValue={spend.payg_cap_minor === null ? "" : spend.payg_cap_minor / 100}
              aria-describedby="ai-cap-hint"
              className="rounded-xl border border-border bg-background px-3 py-2"
            />
            <span id="ai-cap-hint" className="text-xs font-normal text-muted">
              {t("capHint")}
            </span>
          </label>
          {spend.payg_enabled && spend.extra_credits > 0 && (
            <p className="text-sm">
              {t("extraSoFar", { credits: Math.round(spend.extra_credits), amount: money(spend.extra_minor) })}
            </p>
          )}
          <SubmitButton className="self-start px-4 py-2.5">{t("save")}</SubmitButton>
        </form>
      )}
    </section>
  );
}
