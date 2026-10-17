"use client";

import { formatMoney, minorDigits, toMajorUnits, toMinorUnits } from "@business-os/i18n/money";
import { AlertTriangle, Check, Download, Plus, RefreshCw, X } from "lucide-react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useEffect, useId, useRef, useState, useTransition } from "react";

import type { components } from "@business-os/api-client";
import { Pill } from "@/components/pill";

import { acknowledgeWarning, markAccountantChecked, moveStage, refreshRun, startRun, type RunError, type RunResult, type RunStage, typeAmount } from "./actions";

type Run = components["schemas"]["Run"];
type Line = components["schemas"]["RunLine"];
type Item = components["schemas"]["RunItem"];
type Warning = components["schemas"]["RunWarning"];

const STAGES: RunStage[] = ["hours", "additions", "review", "approved"];
const STEPS = ["hours", "additions", "review", "approval", "issue"] as const;

/** Shows the error of the last action and runs the next one inside a transition. */
function useAction() {
  const [error, setError] = useState<RunError | null>(null);
  const [pending, startTransition] = useTransition();
  const run = (action: () => Promise<RunResult>) =>
    startTransition(async () => {
      setError((await action()).error ?? null);
    });
  return { error, pending, run };
}

export function StartRun({ month, label, canManage }: { month: string; label: string; canManage: boolean }) {
  const t = useTranslations("payRun");
  const { error, pending, run } = useAction();
  return (
    <section className="card flex flex-col items-start gap-3 p-6">
      <h3 className="text-lg font-semibold">{t("empty.title")}</h3>
      <p className="max-w-prose text-sm text-muted">{t("empty.body")}</p>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {t(`errors.${error}`)}
        </p>
      )}
      {canManage ? (
        <button type="button" className="btn-primary px-4 py-2" disabled={pending} onClick={() => run(() => startRun(month))}>
          {t("empty.start", { month: label })}
        </button>
      ) : (
        <p className="text-sm text-muted">{t("empty.noRights")}</p>
      )}
    </section>
  );
}

/** Where the run stands: five steps, the last one (issue) comes with the payslips. */
function Stepper({ stage }: { stage: RunStage }) {
  const t = useTranslations("payRun.steps");
  const current = STAGES.indexOf(stage);
  return (
    <ol className="flex flex-wrap items-center gap-2 text-sm" aria-label={t("hours")}>
      {STEPS.map((step, index) => {
        const done = index < current || (stage === "approved" && index <= 3);
        const active = index === current && stage !== "approved";
        return (
          <li key={step} className="flex items-center gap-2" aria-current={active ? "step" : undefined}>
            <span
              className={`inline-flex size-6 items-center justify-center rounded-full text-xs font-semibold ring-1 ${
                done ? "bg-success text-white ring-success" : active ? "bg-primary text-white ring-primary" : "bg-surface text-muted ring-border"
              }`}
            >
              {done ? <Check aria-hidden="true" className="size-3.5" /> : index + 1}
            </span>
            <span className={active ? "font-semibold" : done ? "" : "text-muted"}>{t(step)}</span>
            {index < STEPS.length - 1 && <span aria-hidden="true" className="mx-1 h-px w-6 bg-border" />}
          </li>
        );
      })}
    </ol>
  );
}

export function RunBoard({ run, month, locale, canManage, canApprove }: { run: Run; month: string; locale: string; canManage: boolean; canApprove: boolean }) {
  const t = useTranslations("payRun");
  const { error, pending, run: act } = useAction();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const money = (amount: number) => formatMoney(amount, run.currency, locale);
  const stage = run.stage;
  const index = STAGES.indexOf(stage);
  const next = STAGES[index + 1];
  const nextLabel = stage === "hours" ? t("actions.lock") : stage === "additions" ? t("actions.toReview") : stage === "review" ? t("actions.approve") : null;
  const visible = run.lines.filter((line) => (line.full_name ?? "").toLowerCase().includes(query.trim().toLowerCase()));
  const selected = run.lines.find((line) => line.user_id === open) ?? null;

  const summary = run.summary;
  const change = summary.previous_gross_minor ? (summary.gross_minor - summary.previous_gross_minor) / summary.previous_gross_minor : null;

  // Everything to check, grouped by kind and listing who it concerns.
  const grouped = new Map<string, { severity: Warning["severity"]; names: string[] }>();
  for (const line of run.lines) {
    for (const warning of line.warnings) {
      if (warning.acknowledged) continue;
      const entry = grouped.get(warning.code) ?? { severity: warning.severity, names: [] };
      entry.names.push(line.full_name ?? "");
      grouped.set(warning.code, entry);
    }
  }
  const checks = [...grouped.entries()].sort((a, b) => (a[1].severity === b[1].severity ? 0 : a[1].severity === "error" ? -1 : 1));

  return (
    <div className="flex flex-col gap-6">
      <Stepper stage={stage} />
      <p className="text-sm text-muted">{t(`stageHint.${stage}`)}</p>

      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card p-4">
          <dt className="text-sm text-muted">{t("summary.gross")}</dt>
          <dd className="text-2xl font-semibold tabular-nums">
            <bdi>{money(summary.gross_minor)}</bdi>
          </dd>
          <dd className="text-xs text-muted">
            {change === null
              ? t("summary.noPrevious")
              : t("summary.vsPrevious", { percent: new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 1, signDisplay: "exceptZero" }).format(change) })}
          </dd>
        </div>
        <div className="card p-4">
          <dt className="text-sm text-muted">{t("summary.deductions")}</dt>
          <dd className="text-2xl font-semibold tabular-nums">
            <bdi>{money(summary.deductions_minor)}</bdi>
          </dd>
        </div>
        <div className="card p-4">
          <dt className="text-sm text-muted">{t("summary.people")}</dt>
          <dd className="text-2xl font-semibold tabular-nums">{summary.people}</dd>
        </div>
        <div className="card p-4">
          <dt className="text-sm text-muted">{t("warningsTitle")}</dt>
          <dd className="text-2xl font-semibold tabular-nums">{summary.open_errors + summary.open_warnings}</dd>
          <dd className="text-xs text-muted">{run.payslips_draft ? t("draftNote") : t("accountantDone")}</dd>
        </div>
      </dl>

      {error && (
        <p role="alert" className="text-sm text-danger">
          {t(`errors.${error}`)}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {canManage && stage !== "approved" && nextLabel && next && (stage !== "review" || canApprove) && (
          <button type="button" className="btn-primary px-4 py-2" disabled={pending} onClick={() => act(() => moveStage(month, next))}>
            {nextLabel}
          </button>
        )}
        {stage === "review" && !canApprove && <span className="text-sm text-muted">{t("actions.ownerOnly")}</span>}
        {canManage && index > 0 && stage !== "approved" && (
          <button type="button" className="btn-secondary px-3 py-2 text-sm" disabled={pending} onClick={() => act(() => moveStage(month, STAGES[index - 1]))}>
            {t("actions.back")}
          </button>
        )}
        {canManage && stage !== "approved" && (
          <button type="button" className="btn-ghost px-3 py-2 text-sm" disabled={pending} onClick={() => act(() => refreshRun(month))}>
            <RefreshCw aria-hidden="true" className="size-4" />
            {t("actions.refresh")}
          </button>
        )}
        {canManage && stage !== "approved" && (
          <Link href={`/team/bonuses?month=${month}`} className="btn-secondary px-3 py-2 text-sm">
            <Plus aria-hidden="true" className="size-4" />
            {t("actions.bonus")}
          </Link>
        )}
        <a href={`/team/payroll/export?month=${month}&format=xlsx`} download className="btn-secondary px-3 py-2 text-sm">
          <Download aria-hidden="true" className="size-4" />
          {t("actions.exportXlsx")}
        </a>
        <a href={`/team/payroll/export?month=${month}&format=csv`} download className="btn-ghost px-3 py-2 text-sm">
          {t("actions.exportCsv")}
        </a>
        {stage === "approved" && canApprove && run.payslips_draft && (
          <button type="button" className="btn-secondary px-3 py-2 text-sm" disabled={pending} onClick={() => act(() => markAccountantChecked(month))}>
            {t("accountantMark")}
          </button>
        )}
      </div>

      {run.notes.map((note) => (
        <p key={note.code} className="card flex items-start gap-2 p-3 text-sm">
          <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-warning" />
          <span>{t(`notes.${note.code}` as "notes.no_payroll_file", { names: note.names.join(", ") })}</span>
        </p>
      ))}

      <section aria-labelledby="checks-title" className="flex flex-col gap-2">
        <h3 id="checks-title" className="text-lg font-semibold">
          {t("warningsTitle")}
        </h3>
        {checks.length === 0 ? (
          <p className="text-sm text-muted">{t("warningsNone")}</p>
        ) : (
          <ul className="card divide-y divide-border">
            {checks.map(([code, entry]) => (
              <li key={code} className="flex flex-wrap items-start gap-3 p-3 text-sm">
                <Pill tone={entry.severity === "error" ? "danger" : "warning"}>{entry.severity === "error" ? t("error") : t("warning")}</Pill>
                <span className="flex min-w-0 flex-1 flex-col">
                  <span>{t(`codes.${code}` as "codes.no_bank")}</span>
                  <span dir="auto" className="text-muted">
                    {entry.names.join(", ")}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="people-title" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 id="people-title" className="text-lg font-semibold">
            {t("summary.people")}
          </h3>
          <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} aria-label={t("list.search")} placeholder={t("list.search")} className="field max-w-60" />
        </div>
        {visible.length === 0 ? (
          <p className="text-sm text-muted">{t("list.none")}</p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {visible.map((line) => {
              const left = line.warnings.filter((w) => !w.acknowledged).length;
              return (
                <li key={line.user_id}>
                  <button type="button" onClick={() => setOpen(line.user_id)} className="card flex w-full flex-col gap-1 p-4 text-start transition hover:shadow-md focus-visible:outline-2">
                    <span dir="auto" className="font-medium">
                      {line.full_name}
                    </span>
                    <span className="text-xs text-muted">
                      {t(`types.${line.employment_type}` as "types.global")}
                      {line.employment_type !== "global" && ` · ${t("list.hours", { hours: line.hours.total })}`}
                    </span>
                    <span className="mt-2 flex items-baseline justify-between gap-2">
                      <span className="text-sm text-muted">{t("list.gross")}</span>
                      <bdi className="text-lg font-semibold tabular-nums">{money(line.gross_minor)}</bdi>
                    </span>
                    <span className="text-xs">
                      {left === 0 ? (
                        <Pill tone="success">{t("list.ready")}</Pill>
                      ) : (
                        <Pill tone={line.warnings.some((w) => w.severity === "error" && !w.acknowledged) ? "danger" : "warning"}>{t("list.toCheck", { count: left })}</Pill>
                      )}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {selected && <PaySheet key={selected.user_id} line={selected} month={month} run={run} locale={locale} canManage={canManage && stage !== "approved"} onClose={() => setOpen(null)} />}
    </div>
  );
}

function itemLabel(t: ReturnType<typeof useTranslations>, item: Item): string {
  if (item.section === "component") return item.label;
  if (item.section === "adjustment" || item.section === "deduction") {
    const known = t(`items.${item.code}` as "items.bonus");
    return item.label && item.label !== item.code ? `${known}: ${item.label}` : known;
  }
  return t(`items.${item.code}` as "items.monthly");
}

/** The side sheet: where one person's gross comes from, line by line. */
function PaySheet({ line, month, run, locale, canManage, onClose }: { line: Line; month: string; run: Run; locale: string; canManage: boolean; onClose: () => void }) {
  const t = useTranslations("payRun");
  const dialog = useRef<HTMLDialogElement>(null);
  const { error, pending, run: act } = useAction();
  const money = (amount: number) => formatMoney(amount, run.currency, locale);
  useEffect(() => {
    dialog.current?.showModal();
  }, []);

  const explain = (item: Item): string | null => {
    if (item.quantity && item.unit_minor != null) {
      if (item.section === "component") return t("explain.days", { quantity: item.quantity, unit: money(item.unit_minor) });
      return item.percent ? t("explain.hoursPercent", { quantity: item.quantity, unit: money(item.unit_minor), percent: item.percent }) : t("explain.hours", { quantity: item.quantity, unit: money(item.unit_minor) });
    }
    if (item.code === "monthly" && item.unit_minor != null && item.percent) return t("explain.scope", { unit: money(item.unit_minor), percent: item.percent });
    return null;
  };
  const sections = ["base", "overtime", "component", "adjustment", "deduction"] as const;
  const needsAmount = new Map(line.warnings.filter((w) => w.ref && (w.code === "typed_amount_missing" || w.code === "automatic_rate_missing")).map((w) => [w.ref as string, w]));

  return (
    <dialog
      ref={dialog}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === dialog.current) dialog.current?.close();
      }}
      aria-labelledby="pay-sheet-title"
      className="me-0 ms-auto mb-0 mt-0 h-dvh max-h-none w-[min(30rem,100vw)] border-s border-border bg-surface p-0 text-foreground shadow-2xl backdrop:bg-black/40"
    >
      <div className="flex flex-col gap-5 p-6">
        <div className="flex items-start justify-between gap-3">
          <h2 id="pay-sheet-title" dir="auto" className="text-lg font-semibold">
            {t("sheet.title", { name: line.full_name ?? "" })}
          </h2>
          <button type="button" onClick={() => dialog.current?.close()} aria-label={t("sheet.close")} className="btn-ghost size-8">
            <X aria-hidden="true" className="size-4" />
          </button>
        </div>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {t(`errors.${error}`)}
          </p>
        )}

        {line.warnings.length > 0 && (
          <ul className="flex flex-col gap-2">
            {line.warnings.map((warning) => (
              <li key={warning.key} className="flex flex-wrap items-center gap-2 text-sm">
                <Pill tone={warning.severity === "error" ? "danger" : warning.acknowledged ? "success" : "warning"}>{warning.severity === "error" ? t("error") : warning.acknowledged ? t("acknowledged") : t("warning")}</Pill>
                <span className="min-w-0 flex-1">{t(`codes.${warning.code}` as "codes.no_bank")}</span>
                {canManage && warning.severity === "warning" && (
                  <button type="button" className="btn-ghost px-2 py-1 text-xs" disabled={pending} onClick={() => act(() => acknowledgeWarning(month, line.user_id, warning.key, !warning.acknowledged))}>
                    {warning.acknowledged ? t("undo") : t("acknowledge")}
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}

        <h3 className="text-base font-semibold">{t("sheet.why")}</h3>
        {line.employment_type !== "global" && (
          <p className="text-sm text-muted">
            {t("sheet.hoursLine", { regular: line.hours.regular, tier1: line.hours.tier1, tier2: line.hours.tier2, rest: line.hours.rest_day })}
          </p>
        )}
        {sections.map((section) => {
          const rows = line.items.filter((item) => item.section === section);
          if (rows.length === 0) return null;
          return (
            <section key={section} aria-label={t(`sections.${section}`)} className="flex flex-col gap-1">
              <h4 className="text-sm font-medium text-muted">{t(`sections.${section}`)}</h4>
              <ul className="divide-y divide-border">
                {rows.map((item, position) => {
                  const warning = item.source ? needsAmount.get(item.source) : undefined;
                  const typedNow = item.source ? line.typed[item.source] : undefined;
                  return (
                    <li key={`${item.code}-${position}`} className="flex flex-col gap-1 py-2 text-sm">
                      <div className="flex items-baseline justify-between gap-3">
                        <span dir="auto">{itemLabel(t, item)}</span>
                        <bdi className="font-medium tabular-nums">{money(item.amount_minor)}</bdi>
                      </div>
                      {explain(item) && <span className="text-xs text-muted">{explain(item)}</span>}
                      {canManage && item.source && (warning || typedNow !== undefined) && (
                        <TypedAmount currency={run.currency} initial={typedNow} disabled={pending} onSave={(value) => act(() => typeAmount(month, line.user_id, item.source as string, value))} />
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
        <dl className="flex flex-col gap-1 border-t border-border pt-3 text-sm">
          <div className="flex justify-between gap-3 text-base font-semibold">
            <dt>{t("sheet.gross")}</dt>
            <dd>
              <bdi className="tabular-nums">{money(line.gross_minor)}</bdi>
            </dd>
          </div>
          <div className="flex justify-between gap-3 text-muted">
            <dt>{t("sheet.taxable")}</dt>
            <dd>
              <bdi className="tabular-nums">{money(line.taxable_minor)}</bdi>
            </dd>
          </div>
          <div className="flex justify-between gap-3 text-muted">
            <dt>{t("sheet.socialSecurity")}</dt>
            <dd>
              <bdi className="tabular-nums">{money(line.social_security_minor)}</bdi>
            </dd>
          </div>
          <div className="flex justify-between gap-3 text-muted">
            <dt>{t("sheet.pension")}</dt>
            <dd>
              <bdi className="tabular-nums">{money(line.pension_base_minor)}</bdi>
            </dd>
          </div>
          <div className="flex justify-between gap-3 text-muted">
            <dt>{t("sheet.deductions")}</dt>
            <dd>
              <bdi className="tabular-nums">{money(line.deductions_minor)}</bdi>
            </dd>
          </div>
        </dl>
      </div>
    </dialog>
  );
}

/** A small form for the amount of a component typed in for this month. */
function TypedAmount({ currency, initial, disabled, onSave }: { currency: string; initial: number | undefined; disabled: boolean; onSave: (minor: number | null) => void }) {
  const t = useTranslations("payRun.sheet");
  const id = useId();
  const [value, setValue] = useState(initial === undefined ? "" : toMajorUnits(initial, currency));
  const parsed = value.trim() === "" ? null : toMinorUnits(value, currency);
  return (
    <form
      className="flex flex-wrap items-center gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        if (parsed !== null) onSave(parsed);
      }}
    >
      <label className="sr-only" htmlFor={id}>
        {t("typedLabel")}
      </label>
      <input id={id} inputMode={minorDigits(currency) > 0 ? "decimal" : "numeric"} dir="ltr" value={value} onChange={(event) => setValue(event.target.value)} placeholder={t("typedLabel")} className="field w-36 py-1" />
      <button type="submit" className="btn-secondary px-3 py-1 text-xs" disabled={disabled || parsed === null}>
        {t("save")}
      </button>
      {initial !== undefined && (
        <button type="button" className="btn-ghost px-3 py-1 text-xs" disabled={disabled} onClick={() => onSave(null)}>
          {t("clear")}
        </button>
      )}
    </form>
  );
}
