"use client";

import type { components } from "@business-os/api-client";
import { Check, Copy, Download } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState, useState } from "react";

import { Field, SelectField, TextAreaField } from "@/components/form/field";
import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import { Pill } from "@/components/pill";

import { updateWebsiteOrder } from "./actions";
import { CollapsibleSection } from "@/components/ui/collapsible-section";
import { Button } from "@/components/ui/button";

type Order = components["schemas"]["WebsiteOrder"];

const STAGES = ["received", "building", "review", "live"] as const;

/** One order on the board: its answers, the ready-made prompt for Claude Code and the controls. */
export function OrderCard({ order, price }: { order: Order; price: string }) {
  const t = useTranslations("platform.websites");
  const [state, action] = useActionState(updateWebsiteOrder.bind(null, order.id), {});
  const [copied, setCopied] = useState(false);
  const submitted = order.stage !== "briefing";

  async function copy() {
    await navigator.clipboard.writeText(order.prompt);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <article className="card flex flex-col gap-4 p-4 sm:p-5" aria-label={order.tenant_name}>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold" dir="auto">{order.tenant_name}</h3>
          <p className="text-xs text-muted" dir="auto">{order.contact_name ?? ""} {order.contact_email ?? ""}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Pill tone={order.stage === "live" ? "success" : order.stage === "briefing" ? "muted" : "primary"}>{t(`stages.${order.stage}`)}</Pill>
          {order.change_request && <Pill tone="warning">{t("changesAsked")}</Pill>}
          <span className="text-xs text-muted">{price}</span>
        </div>
      </header>

      {order.change_request && (
        <p className="rounded-xl border border-warning/50 bg-warning/10 p-3 text-sm" dir="auto">
          <span className="font-medium">{t("changesAsked")}: </span>
          {order.change_request}
        </p>
      )}

      {submitted && (
        <CollapsibleSection variant="inline" className="rounded-xl border border-border bg-surface p-3" triggerClassName="font-medium text-primary-ink" title={t("prompt")}>
          <div className="flex flex-wrap gap-2">
            <Button onClick={copy} className="inline-flex items-center gap-2">
              {copied ? <Check aria-hidden="true" className="size-4" /> : <Copy aria-hidden="true" className="size-4" />}
              {copied ? t("copied") : t("copy")}
            </Button>
            <a href={`/platform/website-orders/${order.id}/files`} className="btn-plain btn-secondary inline-flex items-center gap-2 px-3 py-2 text-sm">
              <Download aria-hidden="true" className="size-4" />
              {t("files")}
            </a>
          </div>
          <pre dir="ltr" className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-background p-3 text-xs" tabIndex={0}>{order.prompt}</pre>
        </CollapsibleSection>
      )}

      {submitted ? (
        <form action={action} className="grid gap-3 sm:grid-cols-2">
          <FormFeedback state={state} />
          <SelectField label={t("stage")} name="stage" defaultValue={order.stage} options={STAGES.map((stage) => ({ value: stage, label: t(`stages.${stage}`) }))} />
          <Field label={t("siteUrl")} name="site_url" type="url" dir="ltr" placeholder="https://" defaultValue={order.site_url ?? ""} />
          <TextAreaField label={t("message")} name="message" rows={2} maxLength={2000} defaultValue={order.customer_message ?? ""} />
          <TextAreaField label={t("notes")} name="notes" rows={2} maxLength={4000} defaultValue={order.internal_notes ?? ""} />
          <div className="sm:col-span-2"><SubmitButton>{t("save")}</SubmitButton></div>
        </form>
      ) : (
        <p className="text-sm text-muted">{t("writing")}</p>
      )}
    </article>
  );
}
