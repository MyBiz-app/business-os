"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useId, useState, useTransition } from "react";

import { acknowledgeMfaRisk, type RiskSource } from "@/app/(app)/account/security-actions";
import { useToast } from "@/components/toast/toaster";
import { Modal } from "@/components/ui/modal";

/** The warning about working without two-step sign-in, confirmed with a tick and a button. The API
 * keeps the confirmation as the person's record (who, when, address, browser, version of this text,
 * and `source`: the screen it was given in). Mount it only while it is open. */
export function MfaRiskDialog({ source, onClose, onDone }: { source: RiskSource; onClose: () => void; onDone: () => void }) {
  const t = useTranslations("security.mfa");
  const common = useTranslations("common");
  const toast = useToast();
  const checkId = useId();
  const [checked, setChecked] = useState(false);
  const [pending, startTransition] = useTransition();

  const confirm = () =>
    startTransition(async () => {
      const result = await acknowledgeMfaRisk(source);
      if (!result.ok) {
        toast("error", t("riskError"));
        return;
      }
      toast("success", t("riskDone"));
      onDone();
    });

  return (
    <Modal
      onClose={onClose}
      size="md"
      title={source === "opt_out" ? t("riskDecline") : t("riskTitle")}
      footer={
        <>
          <button type="button" className="btn-secondary px-4 py-2 text-sm" data-autofocus onClick={onClose}>
            {common("cancel")}
          </button>
          <button type="button" className="btn-danger px-4 py-2 text-sm" disabled={!checked || pending} aria-busy={pending} onClick={confirm}>
            {t("riskConfirm")}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4 text-sm leading-relaxed">
        {source === "sensitive_action" && <p className="font-medium">{t("riskActionHint")}</p>}
        <p>{t("riskBody")}</p>
        <label htmlFor={checkId} className="flex items-start gap-2.5 rounded-lg border border-border p-3">
          <input id={checkId} type="checkbox" className="mt-0.5 size-4 shrink-0 accent-primary" checked={checked} onChange={(event) => setChecked(event.target.checked)} />
          <span>{t("riskCheck")}</span>
        </label>
        <Link href="/account#security" onClick={onClose} className="self-start font-medium text-primary-ink underline underline-offset-4">
          {t("riskEnableInstead")}
        </Link>
      </div>
    </Modal>
  );
}
