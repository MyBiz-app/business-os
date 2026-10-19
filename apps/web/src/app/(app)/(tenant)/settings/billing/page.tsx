import { FlaskConical, Sparkles } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import Link from "next/link";
import { redirect } from "next/navigation";

import { SelectField } from "@/components/form/field";
import { Pill } from "@/components/pill";
import { SubmitButton } from "@/components/form/submit-button";
import { unwrap } from "@/lib/api";
import { formatDay } from "@/lib/dates";
import { formatMoney } from "@/lib/money";
import { canManageSettings } from "@/lib/permissions";
import { getTenant } from "@/lib/tenant";

import { addTestCard, endPause, payInvoice, removeCard, resumeSubscription } from "./actions";
import { AiSpend } from "./ai-spend";
import { AiUsers } from "./ai-users";
import { DetailsForm } from "./details-form";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { TopicHeader } from "../topic-header";
import { Ltr } from "@/components/bidi";
import { ScrollRegion } from "@/components/scroll-region";

const TRIAL_DAYS = 14;
const BRANDS = ["visa", "mastercard", "amex"] as const;

export default async function BillingPage({ searchParams }: PageProps<"/settings/billing">) {
  const cancelled = (await searchParams).cancelled === "1";
  const t = await getTranslations("billing");
  const tModules = await getTranslations("modules");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenant();
  if (!canManageSettings(tenant)) redirect("/dashboard");
  const billing = unwrap(await api.GET("/billing", { params: scope }));
  // Only people who manage the AI team see the spend controls (403 for the rest).
  const aiSpend = (await api.GET("/ai/spend", { params: scope })).data;
  const aiUsers = aiSpend ? (await api.GET("/ai/usage/breakdown", { params: scope })).data : undefined;
  const money = (amount: number, currency = billing.estimate.currency) => formatMoney(amount, currency, locale);
  const day = (value: string) => formatDay(value, locale, { day: "numeric", month: "long", year: "numeric" });
  const method = billing.payment_method;
  const collection = billing.collection;
  const usage = billing.usage;
  const number = new Intl.NumberFormat(locale);
  const bytes = (value: number) =>
    value >= 1024 ** 3
      ? new Intl.NumberFormat(locale, { style: "unit", unit: "gigabyte", maximumFractionDigits: 1 }).format(value / 1024 ** 3)
      : new Intl.NumberFormat(locale, { style: "unit", unit: "megabyte", maximumFractionDigits: 1 }).format(value / 1024 ** 2);
  const estimateLines = [
    { key: "core", label: tModules("core"), amount: billing.estimate.core },
    ...Object.entries(billing.estimate.lines).map(([key, amount]) => ({
      key,
      label: tModules(`names.${key as "client_app"}`),
      amount: amount ?? 0,
    })),
  ];

  return (
    <div className="form-columns">
      <TopicHeader title={t("title")} description={t("subtitle")} />

      <p role="note" className="flex items-center gap-2 rounded-xl border border-warning/50 bg-warning/10 px-4 py-2 text-sm">
        <FlaskConical aria-hidden="true" className="size-4 shrink-0" />
        {t("simulated")}
      </p>

      <section aria-labelledby="status-heading" className="card-accent flex flex-col gap-4 p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="status-heading" className="flex items-center gap-2 text-xl font-bold">
            <Sparkles aria-hidden="true" className="size-5 text-primary-ink" />
            {billing.in_trial ? t("trialLeft", { days: billing.trial_days_left }) : t("active")}
          </h2>
          <span className="text-sm text-muted">
            {billing.in_trial
              ? t("firstInvoice", { date: day(billing.next_invoice_on) })
              : t("nextInvoice", { date: day(billing.next_invoice_on) })}
          </span>
        </div>
        <dl className="grid gap-3 sm:grid-cols-3">
          <div className="flex flex-col gap-0.5 rounded-xl bg-foreground/5 px-4 py-3">
            <dt className="text-xs text-muted">{t("summary.plan")}</dt>
            <dd className="text-xl font-bold tabular-nums">
              <bdi>{money(billing.estimate.total)}</bdi>
              <span className="ms-1 text-sm font-medium text-muted">{t("summary.perMonth")}</span>
            </dd>
          </div>
          <div className="flex flex-col gap-0.5 rounded-xl bg-foreground/5 px-4 py-3">
            <dt className="text-xs text-muted">{t("summary.nextPayment")}</dt>
            <dd className="text-xl font-bold">{day(billing.next_invoice_on)}</dd>
          </div>
          <div className="flex flex-col gap-0.5 rounded-xl bg-foreground/5 px-4 py-3">
            <dt className="text-xs text-muted">{t("summary.method")}</dt>
            <dd className="text-xl font-bold">
              {method ? (
                <bdi>
                  {t(`brands.${method.brand}`)} ••{method.last4}
                </bdi>
              ) : (
                <span className="text-base font-medium text-muted">{t("summary.noMethod")}</span>
              )}
            </dd>
          </div>
        </dl>
        {billing.in_trial && (
          <div
            role="progressbar"
            aria-label={t("trialProgress")}
            aria-valuemin={0}
            aria-valuemax={TRIAL_DAYS}
            aria-valuenow={TRIAL_DAYS - billing.trial_days_left}
            className="h-2 overflow-hidden rounded-full bg-foreground/10"
          >
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${Math.round(((TRIAL_DAYS - billing.trial_days_left) / TRIAL_DAYS) * 100)}%` }}
            />
          </div>
        )}
        {billing.balance_due > 0 && (
          <p role="alert" className="rounded-xl border border-danger/40 bg-danger/10 px-4 py-2 text-sm font-medium">
            {t("balanceDue", { amount: money(billing.balance_due) })}
          </p>
        )}
        {collection.state === "read_only" && collection.suspend_on && (
          <p role="alert" className="rounded-xl border border-danger/40 bg-danger/10 px-4 py-2 text-sm font-medium">
            {t("collection.readOnly", { date: day(collection.suspend_on) })}
          </p>
        )}
        {collection.state === "active" && collection.read_only_on && !collection.grace_until && (
          <p role="status" className="rounded-xl border border-warning/50 bg-warning/10 px-4 py-2 text-sm">
            {t("collection.overdue", { date: day(collection.read_only_on) })}
          </p>
        )}
        {collection.grace_until && new Date(collection.grace_until) > new Date() && (
          <p role="status" className="rounded-xl border border-border px-4 py-2 text-sm">
            {t("collection.grace", { date: day(collection.grace_until) })}
          </p>
        )}
      </section>

      <CollapsibleSection
        title={t("plan")}
        defaultOpen
        storageKey="billing-plan-v2"
        actions={
          <Link href="/settings/modules" className="text-sm text-primary-ink underline-offset-4 hover:underline">
            {t("changeModules")}
          </Link>
        }
      >
        <div className="flex flex-col gap-4">
        <ul className="flex flex-col divide-y divide-border text-sm">
          {estimateLines.map((line) => (
            <li key={line.key} className="flex items-center justify-between gap-3 py-2">
              <span>{line.label}</span>
              <bdi className="tabular-nums">{money(line.amount)}</bdi>
            </li>
          ))}
        </ul>
        <p className="flex items-baseline justify-between gap-3 border-t border-border pt-3">
          <span className="font-semibold">{t("perMonth")}</span>
          <bdi className="text-2xl font-bold tabular-nums">{money(billing.estimate.total)}</bdi>
        </p>
        </div>
      </CollapsibleSection>

      <CollapsibleSection title={t("paymentMethod")} storageKey="billing-method-v2">
        <div className="flex flex-col gap-4">
        {method ? (
          <>
            <div
              dir="ltr"
              className="relative flex aspect-[1.7] max-w-xs flex-col justify-between overflow-hidden rounded-2xl bg-gradient-to-br from-navy to-black p-5 text-white shadow-lg"
            >
              <span aria-hidden="true" className="absolute -end-10 -top-10 size-36 rounded-full bg-white/10" />
              <span className="flex items-center justify-between">
                <span className="text-sm font-semibold uppercase tracking-wide">{t(`brands.${method.brand}`)}</span>
                {method.simulated && (
                  <span className="rounded-full bg-warning px-2 py-0.5 text-xs font-bold text-background">{t("testCard")}</span>
                )}
              </span>
              <span className="font-mono text-lg tracking-widest">•••• •••• •••• {method.last4}</span>
              <span className="text-xs opacity-80">{method.exp}</span>
            </div>
            <form action={removeCard}>
              <button type="submit" className="btn-link text-sm text-danger underline-offset-4 hover:underline">
                {t("removeCard")}
              </button>
            </form>
          </>
        ) : (
          <form action={addTestCard} className="flex flex-col gap-3">
            <p className="text-sm text-muted">{t("noCard")}</p>
            <SelectField
              label={t("brand")}
              name="brand"
              defaultValue="visa"
              options={BRANDS.map((brand) => ({ value: brand, label: t(`brands.${brand}`) }))}
            />
            <div>
              <SubmitButton>{t("addTestCard")}</SubmitButton>
            </div>
          </form>
        )}
        </div>
      </CollapsibleSection>

      <CollapsibleSection
        title={t("usage.title", { pack: t(`usage.packs.${usage.pack ?? "included"}`) })}
        description={t("usage.since", { date: day(usage.month_start) })}
        storageKey="billing-usage-v2"
      >
        <div className="flex flex-col gap-4">
        <Meter
          label={t("usage.messages")}
          used={usage.messages}
          included={usage.messages_included}
          text={t("usage.of", { used: number.format(usage.messages), included: number.format(usage.messages_included) })}
        />
        {usage.ai_credits_included > 0 && (
          <Meter
            label={t("usage.ai")}
            used={usage.ai_credits}
            included={usage.ai_credits_included}
            text={t("usage.of", { used: number.format(Math.round(usage.ai_credits)), included: number.format(usage.ai_credits_included) })}
          />
        )}
        <Meter
          label={t("usage.storage")}
          used={usage.storage_bytes}
          included={usage.storage_included_bytes}
          text={t("usage.of", { used: bytes(usage.storage_bytes), included: bytes(usage.storage_included_bytes) })}
        />
        {usage.pack !== "pack_max" && (
          <Link href="/settings/modules" className="self-start text-sm font-medium text-primary-ink underline-offset-4 hover:underline">
            {t("usage.more")}
          </Link>
        )}
        </div>
      </CollapsibleSection>

      {aiSpend && <AiSpend spend={aiSpend} />}
      {aiUsers && <AiUsers breakdown={aiUsers} />}

      <CollapsibleSection title={t("invoices")} storageKey="billing-invoices-v2">
        {billing.invoices.length === 0 ? (
          <p className="text-sm text-muted">{t("noInvoices")}</p>
        ) : (
          <ScrollRegion label={t("invoices")}>
            <table className="w-full text-sm">
              <thead className="text-muted">
                <tr className="border-b border-border">
                  <th scope="col" className="py-2 text-start font-medium">{t("number")}</th>
                  <th scope="col" className="py-2 text-start font-medium">{t("period")}</th>
                  <th scope="col" className="py-2 text-start font-medium">{t("status")}</th>
                  <th scope="col" className="py-2 text-end font-medium">{t("total")}</th>
                  <th scope="col" className="py-2"><span className="sr-only">{t("actions")}</span></th>
                </tr>
              </thead>
              <tbody>
                {billing.invoices.map((invoice) => (
                  <tr key={invoice.id} className="border-b border-border last:border-0">
                    <td className="py-3 tabular-nums"><Ltr>{invoice.number}</Ltr></td>
                    <td className="py-3">
                      {formatDay(invoice.period_start, locale, { day: "numeric", month: "short" })} -{" "}
                      {formatDay(invoice.period_end, locale, { day: "numeric", month: "short", year: "numeric" })}
                    </td>
                    <td className="py-3">
                      <Pill tone={invoice.status === "paid" ? "success" : invoice.status === "open" ? "danger" : "muted"}>
                        {t(`statuses.${invoice.status}`)}
                      </Pill>
                    </td>
                    <td className="py-3 text-end tabular-nums"><bdi>{money(invoice.total, invoice.currency)}</bdi></td>
                    <td className="py-3 text-end">
                      <span className="inline-flex items-center gap-3">
                        {invoice.status === "open" && method && (
                          <form action={payInvoice.bind(null, invoice.id)}>
                            <button type="submit" className="btn-link font-semibold text-primary-ink underline-offset-4 hover:underline">
                              {t("pay")}
                            </button>
                          </form>
                        )}
                        <Link
                          href={`/settings/billing/invoices/${invoice.id}`}
                          className="text-primary-ink underline-offset-4 hover:underline"
                          aria-label={t("viewInvoice", { number: invoice.number })}
                        >
                          {t("view")}
                        </Link>
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
        )}
      </CollapsibleSection>

      <CollapsibleSection title={t("details")} storageKey="billing-details-v2">
        <DetailsForm details={billing.details} />
      </CollapsibleSection>

      <CollapsibleSection title={t("subscription.title")} storageKey="billing-subscription-v2">
        <div className="flex flex-col gap-4">
        {cancelled ? <p className="text-sm font-medium text-success-ink" role="status">{t("cancelFlow.done", { date: collection.cancel_at ? day(collection.cancel_at) : "" })}</p> : null}
        {collection.cancel_at ? (
          <>
            <p className="text-sm">{t("subscription.cancelling", { date: day(collection.cancel_at) })}</p>
            {collection.refund_minor ? (
              <p className="text-sm text-muted">{t("subscription.refund", { amount: money(collection.refund_minor, collection.currency ?? undefined) })}</p>
            ) : null}
            <form action={resumeSubscription}>
              <SubmitButton>{t("subscription.resume")}</SubmitButton>
            </form>
          </>
        ) : (
          <>
            {collection.paused_until ? (
              <>
                <p className="text-sm">{t("subscription.paused", { date: day(collection.paused_until) })}</p>
                <form action={endPause}>
                  <SubmitButton>{t("subscription.endPause")}</SubmitButton>
                </form>
              </>
            ) : null}
            <p className="text-sm text-muted">{t("subscription.hint")}</p>
            {tenant.role === "owner" ? (
              <div>
                <Link href="/settings/billing/cancel" className="btn-link font-medium text-danger underline-offset-4 hover:underline">
                  {t("subscription.cancelStart")}
                </Link>
              </div>
            ) : null}
            <Link href="/legal/cancellation" target="_blank" className="text-sm text-primary-ink underline underline-offset-4">
              {t("subscription.policy")}
            </Link>
          </>
        )}
        </div>
      </CollapsibleSection>

    </div>
  );
}

/** How much of a monthly allowance is used: a bar that turns amber from 80% and red when over. */
function Meter({ label, used, included, text }: { label: string; used: number; included: number; text: string }) {
  const percent = included > 0 ? Math.round((used / included) * 100) : 0;
  const tone = percent >= 100 ? "bg-danger" : percent >= 80 ? "bg-warning" : "bg-primary";
  return (
    <div className="flex flex-col gap-1.5">
      <p className="flex items-baseline justify-between gap-3 text-sm">
        <span className="font-medium">{label}</span>
        <bdi className="tabular-nums text-muted">{text}</bdi>
      </p>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.min(percent, 100)}
        aria-valuetext={text}
        className="h-2 overflow-hidden rounded-full bg-foreground/10"
      >
        <div className={`h-full rounded-full ${tone}`} style={{ width: `${Math.min(Math.max(percent, used > 0 ? 1 : 0), 100)}%` }} />
      </div>
    </div>
  );
}
