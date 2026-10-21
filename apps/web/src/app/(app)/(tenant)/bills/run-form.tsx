"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useActionState, useState } from "react";

import { FormError } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { DataTable } from "@/components/ui/data-table";

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
              <Link href={`/quotes/${bill.id}`} className="font-medium text-primary-ink underline-offset-4 hover:underline" dir="auto">
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
      <DataTable
        label={t("tableCaption")}
        rows={rows}
        rowKey={(row) => row.clientId}
        columns={[
          {
            key: "choose",
            header: <span className="sr-only">{t("choose")}</span>,
            cell: (row) => (
              <input
                type="checkbox"
                name="client_ids"
                value={row.clientId}
                aria-label={t("chooseClient", { name: row.name })}
                checked={chosen.has(row.clientId)}
                disabled={row.billed || !row.billable}
                onChange={() => toggle(row.clientId)}
                className="size-4 accent-[var(--color-primary)]"
              />
            ),
          },
          {
            key: "client",
            header: t("client"),
            rowHeader: true,
            cell: (row) => (
              <>
                <Link href={`/clients/${row.clientId}`} className="underline-offset-4 hover:underline" dir="auto">
                  {row.name}
                </Link>
                {row.billed && <span className="ms-2 rounded-full border border-border px-2 py-0.5 text-xs text-muted">{t("billed")}</span>}
              </>
            ),
          },
          { key: "fee", header: t("fee"), className: "tabular-nums", cell: (row) => row.fee ?? "-" },
          { key: "hours", header: t("hours"), className: "tabular-nums", cell: (row) => row.hours },
          { key: "extra", header: t("extra"), className: "tabular-nums", cell: (row) => row.extra ?? "-" },
          { key: "total", header: t("total"), align: "end", className: "font-semibold tabular-nums", cell: (row) => row.total },
        ]}
      />
      <FormError message={state.error ? t("failed") : undefined} />
      <div>
        <SubmitButton disabled={chosen.size === 0}>{t("run", { count: chosen.size })}</SubmitButton>
      </div>
    </form>
  );
}
