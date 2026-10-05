"use client";

import { CalendarPlus, Receipt, Sparkles } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";
import { useActionState } from "react";

import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { type Catalog, ModulePicker, type Selection } from "@/components/modules/module-picker";

import { type ActionState, extendTrial, setModules, voidInvoice } from "./actions";

type Invoice = { id: string; number: number; total: number; currency: string; status: string };

function useFeedback() {
  const t = useTranslations("platform.actions");
  return (state: ActionState) => (state.error ? t(`errors.${state.error as "generic"}`) : undefined);
}

/** Extend the trial, change the plan, credit an invoice — each one audited for the owner. */
export function BusinessActions({
  tenantId,
  catalog,
  modules,
  activeClients,
  invoices,
}: {
  tenantId: string;
  catalog: Catalog;
  modules: Selection;
  activeClients: number;
  invoices: Invoice[];
}) {
  const t = useTranslations("platform.actions");
  const format = useFormatter();
  const error = useFeedback();
  const [trial, trialAction] = useActionState<ActionState, FormData>(extendTrial.bind(null, tenantId), {});
  const [plan, planAction] = useActionState<ActionState, FormData>(setModules.bind(null, tenantId), {});
  const [credit, creditAction] = useActionState<ActionState, FormData>(voidInvoice.bind(null, tenantId), {});
  const open = invoices.filter((invoice) => invoice.status !== "void");

  return (
    <section aria-labelledby="actions-heading" className="card flex flex-col gap-6 p-6">
      <div className="flex flex-col gap-1">
        <h2 id="actions-heading" className="text-lg font-semibold">
          {t("title")}
        </h2>
        <p className="text-sm text-muted">{t("intro")}</p>
      </div>

      <form action={trialAction} className="flex flex-col gap-3 border-t border-border pt-4">
        <h3 className="flex items-center gap-2 font-medium">
          <CalendarPlus aria-hidden="true" className="size-4 text-primary" />
          {t("trial")}
        </h3>
        <FormError message={error(trial)} />
        <FormNotice
          message={trial.done ? t("trialDone", { date: format.dateTime(new Date(trial.done), { dateStyle: "medium" }) }) : undefined}
        />
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium">{t("trialDays")}</span>
            <input name="days" type="number" min={1} max={180} defaultValue={14} className="control w-28 px-3 py-2" />
          </label>
          <SubmitButton>{t("trial")}</SubmitButton>
        </div>
      </form>

      <form action={planAction} className="flex flex-col gap-3 border-t border-border pt-4">
        <h3 className="flex items-center gap-2 font-medium">
          <Sparkles aria-hidden="true" className="size-4 text-primary" />
          {t("modules")}
        </h3>
        <p className="text-sm text-muted">{t("modulesHint")}</p>
        <FormError message={error(plan)} />
        <FormNotice message={plan.done ? t("modulesDone") : undefined} />
        <ModulePicker catalog={catalog} initial={modules} activeClients={activeClients} name="modules" />
        <div>
          <SubmitButton>{t("modules")}</SubmitButton>
        </div>
      </form>

      <form action={creditAction} className="flex flex-col gap-3 border-t border-border pt-4">
        <h3 className="flex items-center gap-2 font-medium">
          <Receipt aria-hidden="true" className="size-4 text-primary" />
          {t("voidTitle")}
        </h3>
        <p className="text-sm text-muted">{t("voidHint")}</p>
        <FormError message={error(credit)} />
        <FormNotice message={credit.done ? t("voidDone") : undefined} />
        {open.length === 0 ? (
          <p className="text-sm text-muted">{t("noInvoices")}</p>
        ) : (
          <>
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium">{t("voidTitle")}</span>
              <select name="invoice" required className="control w-full px-3 py-2">
                {open.map((invoice) => (
                  <option key={invoice.id} value={invoice.id}>
                    {t("invoice", {
                      number: invoice.number,
                      amount: format.number(invoice.total / 100, { style: "currency", currency: invoice.currency }),
                    })}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium">{t("voidReason")}</span>
              <input name="reason" required minLength={3} maxLength={500} dir="auto" className="control w-full px-3 py-2" />
            </label>
            <div>
              <SubmitButton>{t("void")}</SubmitButton>
            </div>
          </>
        )}
      </form>
    </section>
  );
}
