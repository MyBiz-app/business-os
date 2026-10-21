"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState, useTransition } from "react";

import type { components } from "@business-os/api-client";

import { useToast } from "@/components/toast/toaster";

import { saveMemberAi } from "./ai-actions";

type MemberAi = components["schemas"]["MemberAi"];

/** The AI settings of one person: the switch, their own monthly limit and their daily pace. */
export function AiMemberForm({ ai }: { ai: MemberAi }) {
  const t = useTranslations("staffCard.ai");
  const toast = useToast();
  const [pending, start] = useTransition();
  const [access, setAccess] = useState(ai.has_access);
  const [monthly, setMonthly] = useState(ai.monthly_credits === null ? "" : String(ai.monthly_credits));
  const [daily, setDaily] = useState(ai.daily_percent === null ? "" : String(ai.daily_percent));
  const [error, setError] = useState<string | null>(null);
  const [full, setFull] = useState(false);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setFull(false);
    start(async () => {
      const result = await saveMemberAi(ai.user_id, {
        // Matching what the role gives clears the personal switch, so a later role change still applies.
        ai_access: access === ai.role_default ? null : access,
        monthly_credits: monthly.trim() === "" ? null : Number(monthly),
        daily_percent: daily.trim() === "" ? null : Number(daily),
      });
      if (result.ok) toast("success", t("saved"));
      else {
        setError(t(`errors.${result.error}` as "errors.generic"));
        setFull(result.error === "ai_users_full");
      }
    });
  };

  if (ai.is_owner) return <p className="text-sm text-muted">{t("owner")}</p>;
  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <label className="flex items-center gap-3 text-sm font-medium">
        <input type="checkbox" checked={access} onChange={(e) => setAccess(e.target.checked)} className="size-4" />
        {t("access")}
      </label>
      <p className="-mt-2 text-xs text-muted">{t("accessHint", { count: ai.ai_users_count, allowed: ai.ai_users_allowed })}</p>
      <div className="flex flex-wrap gap-4">
        <label className="flex max-w-xs flex-col gap-1 text-sm font-medium">
          {t("monthly")}
          <input type="number" min={0} step={1} inputMode="numeric" value={monthly} onChange={(e) => setMonthly(e.target.value)} placeholder={t("monthlyPlaceholder")} className="control px-3 py-2" disabled={!access} />
        </label>
        <label className="flex max-w-xs flex-col gap-1 text-sm font-medium">
          {t("daily", { default: ai.default_daily_percent })}
          <input type="number" min={1} max={100} step={1} inputMode="numeric" value={daily} onChange={(e) => setDaily(e.target.value)} placeholder={String(ai.default_daily_percent)} className="control px-3 py-2" disabled={!access} />
        </label>
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
          {full && (
            <>
              {" "}
              <Link href="/settings/billing#ai-users-heading" className="font-semibold underline-offset-4 hover:underline">
                {t("buyExtra")}
              </Link>
            </>
          )}
        </p>
      )}
      <button type="submit" disabled={pending} className="btn-primary w-fit px-4 py-2 text-sm">
        {pending ? t("saving") : t("save")}
      </button>
    </form>
  );
}
