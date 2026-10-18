"use client";

import { Gauge } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import { useState } from "react";

import type { components } from "@business-os/api-client";

import { Modal } from "@/components/ui/modal";

type Meter = components["schemas"]["Meter"];
type Usage = components["schemas"]["app__api__ai_team__Usage"];
type Breakdown = components["schemas"]["UsageBreakdown"];

export type MeterDetails = { usage: Usage; breakdown: Breakdown; people: Record<string, string>; agents: Record<string, string> };

const FILL = { ok: "bg-primary", warn: "bg-warning", over: "bg-danger" } as const;

/** How much of the month's AI is used, against the calendar: the mark on the bar is where an even
 * pace would be today. Managers open the usage window from it; everyone else sees their own allowance. */
export function UsageMeter({ meter, details }: { meter: Meter; details: MeterDetails | null }) {
  const t = useTranslations("aiTeam.meter");
  const locale = useLocale();
  const [open, setOpen] = useState(false);
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 0 });
  const { business, person } = meter;
  const level = business ? business.level : person.level;
  const percent = business ? business.percent : person.day_limit ? (100 * person.used_today) / person.day_limit : 0;
  const shown = Math.min(100, Math.max(0, percent));
  const date = business?.reach_date ? new Intl.DateTimeFormat(locale, { day: "numeric", month: "numeric" }).format(new Date(`${business.reach_date}T00:00:00`)) : null;

  const headline = business ? t("business", { percent: number.format(business.percent) }) : t("person", { percent: number.format(percent) });
  const detail = business
    ? date
      ? t("reach", { date })
      : t("left", { count: business.questions_left ?? 0 })
    : person.questions_left_today !== null
      ? t("leftToday", { count: person.questions_left_today })
      : t("noPace");

  const bar = (
    <div className="flex min-w-0 flex-1 flex-col gap-1.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 text-sm">
        <span className="font-semibold">{headline}</span>
        <span className="text-muted">{detail}</span>
      </div>
      <div role="meter" aria-label={headline} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(shown)} className="relative h-2.5 rounded-full bg-border">
        <div className={`h-full rounded-full ${FILL[level]}`} style={{ width: `${shown}%` }} />
        {business && <span aria-hidden="true" title={t("paceMark")} className="absolute -top-1 -bottom-1 w-0.5 rounded bg-foreground" style={{ insetInlineStart: `${meter.pace_percent}%` }} />}
      </div>
    </div>
  );

  if (!details) return <div className="flex min-w-0 flex-1 items-center gap-3 sm:max-w-md">{bar}</div>;
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} aria-haspopup="dialog" title={t("openWindow")} className="btn-plain flex min-w-0 flex-1 items-center gap-3 rounded-xl px-2 py-1 text-start hover:bg-background sm:max-w-md">
        <Gauge aria-hidden="true" className="size-5 shrink-0 text-muted" />
        {bar}
      </button>
      {open && <UsageWindow meter={meter} details={details} onClose={() => setOpen(false)} />}
    </>
  );
}

function Rows({ rows, label, link }: { rows: { key: string; credits: number }[]; label: (key: string) => string; link?: (key: string) => string | null }) {
  const locale = useLocale();
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  const top = Math.max(1, ...rows.map((r) => r.credits));
  return (
    <ul className="flex flex-col gap-2">
      {rows.map((row) => {
        const href = link?.(row.key);
        return (
          <li key={row.key} className="flex flex-col gap-1 text-sm">
            <div className="flex items-baseline justify-between gap-3">
              <span className="min-w-0 truncate" dir="auto">
                {href ? (
                  <Link href={href} className="text-primary-ink underline-offset-4 hover:underline">
                    {label(row.key)}
                  </Link>
                ) : (
                  label(row.key)
                )}
              </span>
              <span className="tabular-nums text-muted">{number.format(row.credits)}</span>
            </div>
            <div aria-hidden="true" className="h-1.5 rounded-full bg-border">
              <div className="h-full rounded-full bg-primary" style={{ width: `${(100 * row.credits) / top}%` }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function UsageWindow({ meter, details, onClose }: { meter: Meter; details: MeterDetails; onClose: () => void }) {
  const t = useTranslations("aiTeam.meter");
  const locale = useLocale();
  const { usage, breakdown, people, agents } = details;
  const number = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });
  const days = new Map(usage.by_day.map((row) => [row.key, row.credits]));
  const month = meter.month_start.slice(0, 7);
  const series = Array.from({ length: meter.days_in_month }, (_, index) => {
    const day = String(index + 1).padStart(2, "0");
    return { day: index + 1, credits: days.get(`${month}-${day}`) ?? 0 };
  });
  const peak = Math.max(1, ...series.map((d) => d.credits));
  const business = meter.business;

  return (
    <Modal onClose={onClose} title={t("windowTitle")} description={t("windowSubtitle", { used: number.format(usage.credits_used), included: number.format(usage.credits_included) })}>
      <div className="flex flex-col gap-6">
        <section aria-labelledby="usage-days" className="flex flex-col gap-2">
          <h3 id="usage-days" className="font-semibold">
            {t("byDay")}
          </h3>
          <ol className="flex h-28 items-end gap-0.5" aria-label={t("byDay")}>
            {series.map((d) => (
              <li key={d.day} title={`${d.day}: ${number.format(d.credits)}`} className="flex h-full min-w-0 flex-1 items-end">
                <span className={`w-full rounded-t ${d.day === meter.day_of_month ? "bg-primary" : "bg-primary/50"}`} style={{ height: `${Math.max(d.credits > 0 ? 4 : 1, (100 * d.credits) / peak)}%` }} />
              </li>
            ))}
          </ol>
        </section>
        <div className="grid gap-6 md:grid-cols-2">
          <section aria-labelledby="usage-people" className="flex flex-col gap-2">
            <h3 id="usage-people" className="font-semibold">
              {t("byPerson")}
            </h3>
            {usage.by_user.length === 0 ? <p className="text-sm text-muted">{t("none")}</p> : <Rows rows={usage.by_user} label={(key) => people[key] ?? t("unknownPerson")} link={(key) => (people[key] ? `/team/${key}?tab=ai` : null)} />}
          </section>
          <section aria-labelledby="usage-agents" className="flex flex-col gap-2">
            <h3 id="usage-agents" className="font-semibold">
              {t("byAgent")}
            </h3>
            {usage.by_agent.length === 0 ? <p className="text-sm text-muted">{t("none")}</p> : <Rows rows={usage.by_agent} label={(key) => agents[key] ?? key} />}
          </section>
        </div>
        <section aria-labelledby="usage-kind" className="flex flex-col gap-2">
          <h3 id="usage-kind" className="font-semibold">
            {t("byKind")}
          </h3>
          <Rows rows={breakdown.by_kind} label={(key) => t(`kind.${key}` as "kind.asked")} />
        </section>
        <p className="text-sm text-muted">{t("aiUsers", { count: breakdown.ai_users_count, allowed: breakdown.ai_users_allowed })}</p>
        {business && business.level !== "ok" && (
          <p role="status" className="rounded-xl border border-warning/50 bg-warning/10 px-4 py-2 text-sm">
            {t(business.level === "over" ? "alertOver" : "alertWarn")}
          </p>
        )}
        <div className="flex flex-wrap gap-3">
          <Link href="/settings/billing#ai-spend-heading" className="btn-secondary px-3 py-2 text-sm">
            {t("enablePayg")}
          </Link>
          <Link href="/upgrade/ai" className="btn-secondary px-3 py-2 text-sm">
            {t("upgrade")}
          </Link>
          <Link href="/settings/billing#ai-users-heading" className="btn-secondary px-3 py-2 text-sm">
            {t("buyUser")}
          </Link>
          <Link href="/team" className="btn-secondary px-3 py-2 text-sm">
            {t("limitPerson")}
          </Link>
        </div>
      </div>
    </Modal>
  );
}
