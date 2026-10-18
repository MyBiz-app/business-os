"use client";

import { Users } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useState, useTransition } from "react";

import type { components } from "@business-os/api-client";

import { useToast } from "@/components/toast/toaster";
import { formatMoney } from "@/lib/money";

import { saveExtraAiUsers } from "./actions";

type Breakdown = components["schemas"]["UsageBreakdown"];

/** Buying extra AI users: each lets one more person use the AI team and adds credits to the month. */
export function AiUsers({ breakdown }: { breakdown: Breakdown }) {
  const t = useTranslations("billing.aiUsers");
  const locale = useLocale();
  const toast = useToast();
  const [pending, start] = useTransition();
  const [extra, setExtra] = useState(breakdown.extra_ai_users);
  const [error, setError] = useState<string | null>(null);
  const money = (amount: number) => formatMoney(amount, breakdown.currency, locale);
  const needModule = breakdown.ai_users_allowed === 0;

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    start(async () => {
      const result = await saveExtraAiUsers(extra);
      if (result.ok) toast("success", t("saved"));
      else setError(t(result.error === "ai_users_in_use" ? "inUse" : result.error === "ai_module_required" ? "needModule" : "generic"));
    });
  };

  return (
    <section aria-labelledby="ai-users-heading" className="card flex flex-col gap-4 p-6">
      <h2 id="ai-users-heading" className="flex items-center gap-2 text-lg font-semibold">
        <Users aria-hidden="true" className="size-5 text-primary-ink" />
        {t("title")}
      </h2>
      {needModule ? (
        <p className="text-sm">{t("needModule")}</p>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4">
          <p className="text-sm text-muted">{t("intro", { allowed: breakdown.ai_users_allowed, price: money(breakdown.extra_user_price_minor) })}</p>
          <p className="text-sm font-medium">{t("using", { count: breakdown.ai_users_count, allowed: breakdown.ai_users_allowed })}</p>
          <div className="flex items-center gap-3" role="group" aria-label={t("extra")}>
            <button type="button" className="btn-secondary size-10 text-lg" aria-label={t("less")} disabled={extra <= 0 || pending} onClick={() => setExtra(extra - 1)}>
              {"-"}
            </button>
            <output aria-live="polite" className="min-w-10 text-center text-xl font-bold tabular-nums">
              {extra}
            </output>
            <button type="button" className="btn-secondary size-10 text-lg" aria-label={t("more")} disabled={extra >= 200 || pending} onClick={() => setExtra(extra + 1)}>
              {"+"}
            </button>
          </div>
          <p className="text-sm text-muted">
            <bdi>{t("cost", { amount: money(extra * breakdown.extra_user_price_minor) })}</bdi>
          </p>
          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
          <button type="submit" disabled={pending || extra === breakdown.extra_ai_users} className="btn-primary w-fit px-4 py-2 text-sm">
            {t("save")}
          </button>
        </form>
      )}
    </section>
  );
}
