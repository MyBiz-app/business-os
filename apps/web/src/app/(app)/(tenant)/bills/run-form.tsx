"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useActionState, useState } from "react";

import { SubmitButton } from "@/components/form/submit-button";

import { type RunState, runBilling } from "./actions";

type Row = {
  clientId: string;
  name: string;
  fee: string | null;
  hours: string;
  extra: string | null;
  total: string;
  billable: boolean;
  billed: boolean;
};

/** The month's clients with what each would be billed; the chosen ones are billed at once. */
export function RunForm({ month, rows }: { month: string; rows: Row[] }) {
  const t = useTranslations("billingRun");
  const [state, action] = useActionState<RunState, FormData>(runBilling.bind(null, month), {});
  const [chosen, setChosen] = useState(() => new Set(rows.filter((r) => r.billable && !r.billed).map((r) => r.clientId)));
  const toggle = (id: string) =>
    setChosen((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  if (state.billed) {
    return (
      <section role="status" aria-label={t("doneTitle")} className="card flex flex-col gap-3 p-5">
        <h2 className="text-lg font-semibold">{t("done", { count: state.billed.length })}</h2>
        {state.skipped ? <p className="text-sm text-muted">{t("skipped", { count: state.skipped })}</p> : null}
        <ul className="flex flex-col divide-y divide-border text-sm">
          {state.billed.map((bill) => (
            <li key={bill.id} className="flex justify-between gap-3 py-2">
              <Link href={`/quotes/${bill.id}`} className="font-medium text-primary underline-offset-4 hover:underline" dir="auto">
                {t("billFor", { number: bill.number, name: bill.client })}
              </Link>
              <span className="tabular-nums">{bill.total}</span>
            </li>
          ))}
        </ul>
      </section>
    );
  }

  return (
    <form action={action} className="flex flex-col gap-4">
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">{t("tableCaption")}</caption>
          <thead className="text-muted">
            <tr className="border-b border-border text-start">
              <th scope="col" className="p-3 text-start">
                <span className="sr-only">{t("choose")}</span>
              </th>
              <th scope="col" className="p-3 text-start font-medium">{t("client")}</th>
              <th scope="col" className="p-3 text-start font-medium">{t("fee")}</th>
              <th scope="col" className="p-3 text-start font-medium">{t("hours")}</th>
              <th scope="col" className="p-3 text-start font-medium">{t("extra")}</th>
              <th scope="col" className="p-3 text-end font-medium">{t("total")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const disabled = row.billed || !row.billable;
              return (
                <tr key={row.clientId} className="border-b border-border last:border-0">
                  <td className="p-3">
                    <input
                      type="checkbox"
                      name="client_ids"
                      value={row.clientId}
                      aria-label={t("chooseClient", { name: row.name })}
                      checked={chosen.has(row.clientId)}
                      disabled={disabled}
                      onChange={() => toggle(row.clientId)}
                      className="size-4 accent-[var(--color-primary)]"
                    />
                  </td>
                  <th scope="row" className="p-3 text-start font-medium">
                    <Link href={`/clients/${row.clientId}`} className="underline-offset-4 hover:underline" dir="auto">
                      {row.name}
                    </Link>
                    {row.billed && <span className="ms-2 rounded-full border border-border px-2 py-0.5 text-xs text-muted">{t("billed")}</span>}
                  </th>
                  <td className="p-3 tabular-nums">{row.fee ?? "—"}</td>
                  <td className="p-3 tabular-nums">{row.hours}</td>
                  <td className="p-3 tabular-nums">{row.extra ?? "—"}</td>
                  <td className="p-3 text-end font-semibold tabular-nums">{row.total}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {state.error && (
        <p role="alert" className="text-sm text-danger">
          {t("failed")}
        </p>
      )}
      <div>
        <SubmitButton disabled={chosen.size === 0}>{t("run", { count: chosen.size })}</SubmitButton>
      </div>
    </form>
  );
}
