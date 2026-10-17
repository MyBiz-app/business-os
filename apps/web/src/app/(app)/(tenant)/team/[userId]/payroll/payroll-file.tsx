"use client";

import { formatMoney, toMajorUnits, toMinorUnits } from "@business-os/i18n/money";
import { useTranslations } from "next-intl";
import { useState, useTransition } from "react";

import { Field, SelectField } from "@/components/form/field";
import { IdentityEditor } from "@/components/identity-editor";
import type { components } from "@business-os/api-client";

import {
  type EmploymentInput,
  type PayrollError,
  overrideCreditPoints,
  requestForm101,
  revealBank,
  saveEmployment,
} from "./actions";

type Employment = components["schemas"]["Employment"];
type FormSummary = components["schemas"]["Form101Summary"];
type Tab = "personal" | "terms" | "components" | "documents";
const TABS: Tab[] = ["personal", "terms", "components", "documents"];

/** One team member's payroll file: four tabs (personal details and Form 101, terms of
 * employment, pay components, documents). Amounts are never computed here; the API does that. */
export function PayrollFile(props: {
  userId: string;
  name: string;
  currency: string;
  locale: string;
  employment: Employment;
  forms: FormSummary[];
  canManage: boolean;
  thisYear: number;
}) {
  const t = useTranslations("payroll");
  const [tab, setTab] = useState<Tab>("personal");
  return (
    <div className="flex flex-col gap-4">
      <div role="tablist" aria-label={t("tabsLabel")} className="flex flex-wrap gap-1 border-b border-border">
        {TABS.map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            id={`payroll-tab-${key}`}
            aria-selected={tab === key}
            aria-controls={`payroll-panel-${key}`}
            onClick={() => setTab(key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              tab === key ? "border-primary text-primary" : "border-transparent text-muted hover:text-foreground"
            }`}
          >
            {t(`tabs.${key}`)}
          </button>
        ))}
      </div>
      <section role="tabpanel" id={`payroll-panel-${tab}`} aria-labelledby={`payroll-tab-${tab}`} className="card flex flex-col gap-6 p-6">
        {tab === "personal" && <Personal {...props} />}
        {tab === "terms" && <Terms {...props} />}
        {tab === "components" && <p className="text-sm text-muted">{t("components.soon")}</p>}
        {tab === "documents" && <Documents {...props} />}
      </section>
    </div>
  );
}

function ErrorLine({ error }: { error: PayrollError | null }) {
  const t = useTranslations("payroll");
  if (!error) return null;
  return (
    <p role="alert" className="text-sm text-danger">
      {t(`errors.${error}`)}
    </p>
  );
}

function Personal({ userId, name, employment, forms, canManage, thisYear }: Parameters<typeof PayrollFile>[0]) {
  const t = useTranslations("payroll");
  const [bank, setBank] = useState<string | null>(null);
  const [error, setError] = useState<PayrollError | null>(null);
  const [pending, startTransition] = useTransition();
  const hasThisYear = forms.some((form) => form.tax_year === thisYear);

  return (
    <>
      <div className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">{t("personal.idTitle")}</h2>
        <IdentityEditor subject={{ kind: "member", id: userId }} />
      </div>

      <div className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold">{t("personal.bankTitle")}</h2>
        {employment.bank_last4 ? (
          <p className="flex flex-wrap items-center gap-3 text-sm">
            <bdi dir="ltr">{bank ?? `•••${employment.bank_last4}`}</bdi>
            {employment.can_reveal_bank && (
              <button
                type="button"
                className="text-primary underline-offset-4 hover:underline"
                disabled={pending}
                onClick={() =>
                  bank
                    ? setBank(null)
                    : startTransition(async () => {
                        const result = await revealBank(userId);
                        if (result.data) setBank(`${result.data.bank_code}-${result.data.branch}-${result.data.account}`);
                        else setError(result.error ?? "generic");
                      })
                }
              >
                {bank ? t("personal.hide") : t("personal.show")}
              </button>
            )}
          </p>
        ) : (
          <p className="text-sm text-muted">{t("personal.noBank")}</p>
        )}
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">{t("form101.title")}</h2>
          {canManage && !hasThisYear && (
            <button
              type="button"
              className="btn-secondary px-3 py-1.5 text-sm"
              disabled={pending}
              onClick={() =>
                startTransition(async () => {
                  const result = await requestForm101(userId, thisYear);
                  setError(result.error ?? null);
                })
              }
            >
              {t("form101.request", { year: thisYear, name })}
            </button>
          )}
        </div>
        <p className="text-sm text-muted">{t("form101.hint")}</p>
        <ErrorLine error={error} />
        {forms.length === 0 ? <p className="text-sm text-muted">{t("form101.none")}</p> : null}
        <ul className="flex flex-col divide-y divide-border">
          {forms.map((form) => (
            <FormRow key={form.tax_year} userId={userId} form={form} canManage={canManage} />
          ))}
        </ul>
      </div>
    </>
  );
}

function FormRow({ userId, form, canManage }: { userId: string; form: FormSummary; canManage: boolean }) {
  const t = useTranslations("payroll");
  const [editing, setEditing] = useState(false);
  const [points, setPoints] = useState(form.override_points ?? form.computed_points ?? "");
  const [note, setNote] = useState(form.override_note ?? "");
  const [error, setError] = useState<PayrollError | null>(null);
  const [pending, startTransition] = useTransition();
  const submitted = form.status === "submitted";

  function save(value: number | null) {
    startTransition(async () => {
      const result = await overrideCreditPoints(userId, form.tax_year, value, note);
      setError(result.error ?? null);
      if (result.ok) setEditing(false);
    });
  }

  return (
    <li className="flex flex-col gap-2 py-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium">{t("form101.year", { year: form.tax_year })}</span>
        <span className={submitted ? "text-success" : "text-muted"}>{t(`form101.status.${form.status}`)}</span>
        {submitted && (
          <span>
            {t("form101.points")}: <bdi>{form.credit_points}</bdi>
            {form.override_points != null && <span className="text-muted"> ({t("form101.adjusted")})</span>}
          </span>
        )}
        {submitted && (
          <span className="flex items-center gap-3">
            {canManage && (
              <button type="button" className="text-primary underline-offset-4 hover:underline" onClick={() => setEditing(!editing)}>
                {t("form101.adjust")}
              </button>
            )}
            <a className="text-primary underline-offset-4 hover:underline" href={`/team/${userId}/payroll/form101/${form.tax_year}/pdf`} download>
              {t("form101.pdf")}
            </a>
          </span>
        )}
      </div>
      {submitted && form.signed_name && <p className="text-xs text-muted">{t("form101.signedBy", { name: form.signed_name })}</p>}
      {editing && (
        <form
          className="flex flex-col gap-3 rounded-xl bg-surface-muted p-3"
          onSubmit={(event) => {
            event.preventDefault();
            const value = Number(points);
            if (Number.isNaN(value) || value < 0) return setError("invalid");
            save(value);
          }}
        >
          <Field label={t("form101.points")} type="number" step="0.25" min="0" value={points} onChange={(event) => setPoints(event.target.value)} />
          <Field label={t("form101.note")} value={note} maxLength={500} onChange={(event) => setNote(event.target.value)} />
          <ErrorLine error={error} />
          <div className="flex gap-2">
            <button type="submit" className="btn-primary px-3 py-1.5 text-sm" disabled={pending}>
              {t("save")}
            </button>
            {form.override_points != null && (
              <button type="button" className="btn-ghost px-3 py-1.5 text-sm" disabled={pending} onClick={() => save(null)}>
                {t("form101.clear")}
              </button>
            )}
          </div>
        </form>
      )}
    </li>
  );
}

function Terms({ userId, currency, locale, employment, canManage }: Parameters<typeof PayrollFile>[0]) {
  const t = useTranslations("payroll");
  const [type, setType] = useState(employment.employment_type);
  const [monthly, setMonthly] = useState(employment.monthly_amount_minor != null ? toMajorUnits(employment.monthly_amount_minor, currency) : "");
  const [hourly, setHourly] = useState(employment.hourly_rate_minor != null ? toMajorUnits(employment.hourly_rate_minor, currency) : "");
  const [scope, setScope] = useState(String(employment.scope_pct));
  const [start, setStart] = useState(employment.start_date ?? "");
  const [days, setDays] = useState(String(employment.work_days_per_week));
  const [jobTitle, setJobTitle] = useState(employment.job_title ?? "");
  const [notice, setNotice] = useState(employment.employment_notice_date ?? "");
  const [fund, setFund] = useState(employment.pension?.fund_name ?? "");
  const [employee, setEmployee] = useState(String(employment.pension?.employee_pct ?? 6));
  const [employer, setEmployer] = useState(String(employment.pension?.employer_pct ?? 6.5));
  const [severance, setSeverance] = useState(String(employment.pension?.severance_pct ?? 6));
  const [bankCode, setBankCode] = useState("");
  const [branch, setBranch] = useState("");
  const [account, setAccount] = useState("");
  const [error, setError] = useState<PayrollError | null>(null);
  const [saved, setSaved] = useState(false);
  const [pending, startTransition] = useTransition();

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const monthlyMinor = monthly === "" ? null : toMinorUnits(monthly, currency);
    const hourlyMinor = hourly === "" ? null : toMinorUnits(hourly, currency);
    if (monthlyMinor === null && monthly !== "") return setError("invalid");
    if (hourlyMinor === null && hourly !== "") return setError("invalid");
    const bank = bankCode || branch || account ? { bank_code: bankCode, branch, account } : null;
    const input: EmploymentInput = {
      employment_type: type,
      currency,
      monthly_amount_minor: type === "hourly" ? null : monthlyMinor,
      hourly_rate_minor: type === "global" ? null : hourlyMinor,
      scope_pct: Number(scope),
      start_date: start || null,
      work_days_per_week: Number(days),
      job_title: jobTitle || null,
      pension: { fund_name: fund || null, employee_pct: Number(employee), employer_pct: Number(employer), severance_pct: Number(severance) },
      employment_notice_date: notice || null,
      bank,
    };
    startTransition(async () => {
      const result = await saveEmployment(userId, input);
      setError(result.error ?? null);
      setSaved(Boolean(result.ok));
    });
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-5">
      <fieldset disabled={!canManage} className="grid gap-4 sm:grid-cols-2">
        <SelectField
          label={t("terms.type")}
          value={type}
          onChange={(event) => setType(event.target.value as typeof type)}
          options={(["global", "hourly", "global_overtime"] as const).map((value) => ({ value, label: t(`terms.types.${value}`) }))}
        />
        <Field label={t("terms.jobTitle")} value={jobTitle} onChange={(event) => setJobTitle(event.target.value)} maxLength={120} />
        {type !== "hourly" && (
          <Field
            label={t("terms.monthly", { currency })}
            hint={employment.monthly_amount_minor != null ? formatMoney(employment.monthly_amount_minor, currency, locale) : undefined}
            inputMode="decimal"
            value={monthly}
            onChange={(event) => setMonthly(event.target.value)}
          />
        )}
        {type !== "global" && (
          <Field label={t("terms.hourly", { currency })} inputMode="decimal" value={hourly} onChange={(event) => setHourly(event.target.value)} />
        )}
        <Field label={t("terms.scope")} type="number" min="1" max="100" step="0.5" value={scope} onChange={(event) => setScope(event.target.value)} />
        <SelectField
          label={t("terms.days")}
          value={days}
          onChange={(event) => setDays(event.target.value)}
          options={[5, 6, 7, 4, 3, 2, 1].map((n) => ({ value: String(n), label: String(n) }))}
        />
        <Field label={t("terms.start")} type="date" value={start} onChange={(event) => setStart(event.target.value)} />
        <Field label={t("terms.notice")} type="date" value={notice} onChange={(event) => setNotice(event.target.value)} />
      </fieldset>

      <fieldset disabled={!canManage} className="grid gap-4 sm:grid-cols-2">
        <legend className="mb-2 text-sm font-semibold">{t("terms.pension")}</legend>
        <Field label={t("terms.fund")} value={fund} onChange={(event) => setFund(event.target.value)} maxLength={120} />
        <Field label={t("terms.employeePct")} type="number" min="0" max="100" step="0.1" value={employee} onChange={(event) => setEmployee(event.target.value)} />
        <Field label={t("terms.employerPct")} type="number" min="0" max="100" step="0.1" value={employer} onChange={(event) => setEmployer(event.target.value)} />
        <Field label={t("terms.severancePct")} type="number" min="0" max="100" step="0.1" value={severance} onChange={(event) => setSeverance(event.target.value)} />
      </fieldset>

      <fieldset disabled={!canManage} className="grid gap-4 sm:grid-cols-3">
        <legend className="mb-2 text-sm font-semibold">{t("terms.bank")}</legend>
        <Field label={t("terms.bankCode")} inputMode="numeric" value={bankCode} onChange={(event) => setBankCode(event.target.value)} hint={employment.bank_last4 ? t("terms.bankKept") : undefined} />
        <Field label={t("terms.branch")} inputMode="numeric" value={branch} onChange={(event) => setBranch(event.target.value)} />
        <Field label={t("terms.account")} inputMode="numeric" value={account} onChange={(event) => setAccount(event.target.value)} />
      </fieldset>

      <ErrorLine error={error} />
      {saved && <p role="status" className="text-sm text-success">{t("saved")}</p>}
      {canManage && (
        <div>
          <button type="submit" className="btn-primary px-4 py-2" disabled={pending}>
            {t("save")}
          </button>
        </div>
      )}
    </form>
  );
}

function Documents({ userId, forms, employment }: Parameters<typeof PayrollFile>[0]) {
  const t = useTranslations("payroll");
  const signed = forms.filter((form) => form.status === "submitted");
  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold">{t("documents.title")}</h2>
      <ul className="flex flex-col divide-y divide-border text-sm">
        {signed.map((form) => (
          <li key={form.tax_year} className="flex items-center justify-between gap-3 py-2.5">
            <span>{t("form101.year", { year: form.tax_year })}</span>
            <a className="text-primary underline-offset-4 hover:underline" href={`/team/${userId}/payroll/form101/${form.tax_year}/pdf`} download>
              {t("form101.pdf")}
            </a>
          </li>
        ))}
        <li className="flex items-center justify-between gap-3 py-2.5">
          <span>{t("documents.notice")}</span>
          <span className="text-muted">{employment.employment_notice_date ?? t("documents.notSent")}</span>
        </li>
      </ul>
      {signed.length === 0 && <p className="text-sm text-muted">{t("documents.none")}</p>}
      <p className="text-xs text-muted">{t("documents.more")}</p>
    </div>
  );
}
