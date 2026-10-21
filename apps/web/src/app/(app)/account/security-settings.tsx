"use client";

import { ShieldCheck } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useActionState, useState } from "react";

import { Field } from "@/components/form/field";
import { FormError, FormNotice } from "@/components/form/form-message";
import { SubmitButton } from "@/components/form/submit-button";
import { MfaRiskDialog } from "@/components/mfa-risk-dialog";
import { CODE_LENGTH } from "@/lib/mfa";

import { confirmEnrollment, type EnrollState, type RemoveState, removeFactor, signOutEverywhere, startEnrollment } from "./security-actions";

export type Factor = { id: string; createdAt: string };
export type Device = { id: string; label: string; lastSeenAt: string; current: boolean };

/** The person's security: the authenticator app, signing out everywhere and the recent devices. */
export function SecuritySettings({
  factors,
  devices,
  required,
  riskOptional,
  riskAcknowledged,
}: {
  factors: Factor[];
  devices: Device[];
  required: "team" | "business" | null;
  /** Owners and managers may work without a code once they confirm the warning (not the MyBiz team). */
  riskOptional: boolean;
  riskAcknowledged: boolean;
}) {
  const t = useTranslations("security");
  const locale = useLocale();
  const [enrollment, start] = useActionState<EnrollState>(startEnrollment, {});
  const [confirmed, confirm] = useActionState<EnrollState, FormData>(confirmEnrollment, enrollment);
  const [removal, remove] = useActionState<RemoveState, FormData>(removeFactor, {});
  const [declining, setDeclining] = useState(false);
  const router = useRouter();
  const scanning = Boolean(enrollment.factorId) && !confirmed.done;
  const when = (iso: string) => new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));

  return (
    <div className="flex flex-col gap-6">
      {required && factors.length === 0 && (
        <FormError message={t(required === "team" ? "mfa.requiredTeam" : "mfa.requiredBusiness")} />
      )}
      <div className="flex flex-col gap-3">
        <h3 className="flex items-center gap-2 font-medium">
          <ShieldCheck aria-hidden="true" className="size-5 text-primary-ink" />
          {t("mfa.title")}
          <span className="pill text-xs">{factors.length > 0 ? t("mfa.on") : t("mfa.off")}</span>
        </h3>
        <p className="text-sm text-muted">{t("mfa.hint")}</p>
        <FormNotice message={confirmed.done ? t("mfa.enabled") : removal.done ? t("mfa.removed") : undefined} />
        <FormError message={removal.error && t(`errors.${removal.error}` as "errors.generic")} />
        {factors.length > 0 && (
          <ul className="flex flex-col divide-y divide-border">
            {factors.map((factor, index) => (
              <li key={factor.id} className="flex flex-wrap items-center justify-between gap-3 py-2 text-sm">
                <span>
                  {t("mfa.factorLabel", { number: index + 1 })} <span className="text-muted">{when(factor.createdAt)}</span>
                </span>
                <form action={remove}>
                  <input type="hidden" name="factor" value={factor.id} />
                  <SubmitButton variant="secondary" className="px-3 py-1.5 text-sm">
                    {t("mfa.remove")}
                  </SubmitButton>
                </form>
              </li>
            ))}
          </ul>
        )}
        {scanning ? (
          <form action={confirm} className="flex flex-col gap-4">
            <input type="hidden" name="factor" value={enrollment.factorId} />
            <p className="text-sm">{t("mfa.scan")}</p>
            {/* eslint-disable-next-line @next/next/no-img-element -- the QR code is a data: image from Supabase */}
            <img src={enrollment.qr} alt="" width={176} height={176} className="size-44 rounded-lg bg-white p-2" />
            <p className="text-sm text-muted">
              {t("mfa.secret")} <code dir="ltr" className="select-all break-all">{enrollment.secret}</code>
            </p>
            <FormError message={confirmed.error && t(`errors.${confirmed.error}` as "errors.generic")} />
            <Field label={t("mfa.code")} name="code" inputMode="numeric" autoComplete="one-time-code" maxLength={CODE_LENGTH} dir="ltr" required />
            <SubmitButton>{t("mfa.confirm")}</SubmitButton>
          </form>
        ) : (
          <form action={start}>
            <FormError message={enrollment.error && t(`errors.${enrollment.error}` as "errors.generic")} />
            <SubmitButton variant={factors.length > 0 ? "secondary" : "primary"}>{factors.length > 0 ? t("mfa.addBackup") : t("mfa.enable")}</SubmitButton>
          </form>
        )}
        {factors.length === 1 && <p className="text-xs text-muted">{t("mfa.backupHint")}</p>}
        {factors.length === 0 && riskOptional && (
          <div className="flex flex-col gap-2 rounded-lg border border-border p-4">
            <h4 className="font-medium">{t("mfa.riskTitle")}</h4>
            <p className="text-sm text-muted">{t("mfa.riskBody")}</p>
            {riskAcknowledged ? (
              <p className="text-sm font-medium">{t("mfa.riskChosen")}</p>
            ) : (
              <button type="button" className="btn-secondary self-start px-4 py-2 text-sm" onClick={() => setDeclining(true)}>
                {t("mfa.riskDecline")}
              </button>
            )}
            {declining && (
              <MfaRiskDialog
                source="settings"
                onClose={() => setDeclining(false)}
                onDone={() => {
                  setDeclining(false);
                  router.refresh();
                }}
              />
            )}
          </div>
        )}
      </div>
      <div className="flex flex-col gap-3 border-t border-border pt-6">
        <h3 className="font-medium">{t("signOutAll.title")}</h3>
        <p className="text-sm text-muted">{t("signOutAll.hint")}</p>
        <form action={signOutEverywhere}>
          <SubmitButton variant="secondary">{t("signOutAll.button")}</SubmitButton>
        </form>
      </div>
      <div className="flex flex-col gap-3 border-t border-border pt-6">
        <h3 className="font-medium">{t("devices.title")}</h3>
        <p className="text-sm text-muted">{t("devices.hint")}</p>
        {devices.length === 0 ? (
          <p className="text-sm text-muted">{t("devices.empty")}</p>
        ) : (
          <ul className="flex flex-col divide-y divide-border">
            {devices.map((device) => (
              <li key={device.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                <span dir="auto" className="font-medium">
                  {device.label || "-"}
                  {device.current && <span className="pill ms-2 text-xs">{t("devices.current")}</span>}
                </span>
                <span className="text-muted">{t("devices.lastSeen", { when: when(device.lastSeenAt) })}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
