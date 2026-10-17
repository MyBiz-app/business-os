"use client";

import { formatMoney } from "@business-os/i18n/money";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useState, useTransition } from "react";

import type { components } from "@business-os/api-client";

import { type BonusError, decideBonus, removeAdjustment } from "./actions";

type Adjustment = components["schemas"]["Adjustment"];

/** The month's one-off amounts. Proposals wait here for the owner's decision. */
export function BonusList({
  currency,
  locale,
  month,
  rows,
  canApprove,
  canManage,
}: {
  currency: string;
  locale: string;
  month: string;
  rows: Adjustment[];
  canApprove: boolean;
  canManage: boolean;
}) {
  const t = useTranslations("payBonuses");
  const [error, setError] = useState<BonusError | null>(null);
  const [pending, startTransition] = useTransition();
  const waiting = [...new Set(rows.filter((row) => row.status === "proposed").map((row) => row.batch_id))];

  function run(action: () => Promise<{ error?: BonusError }>) {
    startTransition(async () => setError((await action()).error ?? null));
  }

  return (
    <section aria-labelledby="bonus-list" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="bonus-list" className="text-lg font-semibold">
          {t("listTitle")}
        </h2>
        <nav aria-label={t("month")} className="flex gap-3 text-sm">
          <Link className="text-primary-ink underline-offset-4 hover:underline" href={`/team/bonuses?month=${shift(month, -1)}`}>
            {shift(month, -1)}
          </Link>
          <bdi>{month}</bdi>
          <Link className="text-primary-ink underline-offset-4 hover:underline" href={`/team/bonuses?month=${shift(month, 1)}`}>
            {shift(month, 1)}
          </Link>
        </nav>
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {t(`errors.${error}`)}
        </p>
      )}
      {canApprove &&
        waiting.map((batch) => {
          const lines = rows.filter((row) => row.batch_id === batch);
          const total = lines.reduce((sum, row) => sum + row.amount_minor, 0);
          return (
          <div key={batch} className="card flex flex-wrap items-center justify-between gap-3 p-4 text-sm">
            <span className="flex flex-col">
              <span className="font-medium">{t("status.proposed")}: {t(`kinds.${lines[0].kind}`)}, <bdi>{formatMoney(total, currency, locale)}</bdi></span>
              <span className="text-muted">{lines.map((row) => row.full_name).join(", ")}</span>
            </span>
            <span className="flex gap-2">
              <button type="button" className="btn-primary px-3 py-1.5" disabled={pending} onClick={() => run(() => decideBonus(batch, true))}>
                {t("approve")}
              </button>
              <button type="button" className="btn-ghost px-3 py-1.5" disabled={pending} onClick={() => run(() => decideBonus(batch, false))}>
                {t("reject")}
              </button>
            </span>
          </div>
          );
        })}
      {rows.length === 0 ? (
        <p className="text-sm text-muted">{t("none")}</p>
      ) : (
        <ul className="card divide-y divide-border">
          {rows.map((row) => (
            <li key={row.id} className="flex flex-wrap items-center justify-between gap-2 p-4 text-sm">
              <div className="flex flex-col">
                <span className="font-medium">
                  {row.full_name} <span className="text-muted">({t(`kinds.${row.kind}`)})</span>
                </span>
                {row.note && <span className="text-muted">{row.note}</span>}
              </div>
              <span className="flex items-center gap-4">
                <bdi className={row.kind === "deduction" ? "text-danger" : undefined}>{formatMoney(row.amount_minor, row.currency || currency, locale)}</bdi>
                <span className={row.status === "approved" ? "text-success-ink" : "text-muted"}>{t(`status.${row.status}`)}</span>
                {(canManage || row.status === "proposed") && (
                  <button type="button" className="btn-link text-danger underline-offset-4 hover:underline" disabled={pending} onClick={() => run(() => removeAdjustment(row.id))}>
                    {t("remove")}
                  </button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** The month before or after "YYYY-MM". */
function shift(month: string, by: number) {
  const [year, number] = month.split("-").map(Number);
  const date = new Date(Date.UTC(year, number - 1 + by, 1));
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
}
