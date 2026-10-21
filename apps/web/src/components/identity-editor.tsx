"use client";

import { israeliIdValid, maskedId } from "@business-os/i18n/israeli-id";
import { useTranslations } from "next-intl";
import { useEffect, useState, useTransition } from "react";

import {
  type IdentityResult,
  type IdentitySubject,
  type IdentityView,
  loadIdentity,
  removeIdentity,
  revealIdentity,
  saveIdentity,
} from "@/app/(app)/(tenant)/identity-actions";
import { Field, SelectField } from "@/components/form/field";
import { useConfirm } from "@/components/ui/confirm-dialog";

type IdType = "il_id" | "passport" | "foreign";

/** One person's ID number: masked by default, shown in full only on request (which is logged),
 * saved with the Israeli check digit verified before it leaves the browser. */
export function IdentityEditor({ subject, initial }: { subject: IdentitySubject; initial?: IdentityView }) {
  const t = useTranslations("identity");
  const confirm = useConfirm();
  const [view, setView] = useState<IdentityView | null>(initial ?? null);
  const [revealed, setRevealed] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [idType, setIdType] = useState<IdType>("il_id");
  const [number, setNumber] = useState("");
  const [country, setCountry] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    if (initial) return;
    let live = true;
    void loadIdentity(subject).then((result) => {
      if (!live) return;
      if (result.identity) setView(result.identity);
      else setError(t(`errors.${result.error ?? "generic"}`));
    });
    return () => {
      live = false;
    };
  }, [initial, subject, t]);

  function apply(result: IdentityResult, done?: () => void) {
    if (result.error) return setError(t(`errors.${result.error}`));
    setError(null);
    if (result.identity) setView(result.identity);
    done?.();
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (idType === "il_id" && !israeliIdValid(number)) return setError(t("errors.invalid_id_number"));
    if (idType !== "il_id" && !/^[A-Za-z]{2}$/.test(country.trim())) return setError(t("errors.invalid_id_country"));
    startTransition(async () => {
      apply(await saveIdentity(subject, { id_type: idType, number, country }), () => {
        setEditing(false);
        setRevealed(null);
        setNumber("");
      });
    });
  }

  if (!view) {
    return <p className="text-sm text-muted">{error ?? t("loading")}</p>;
  }

  const manageable = view.mode !== "off";

  return (
    <div className="flex flex-col gap-3">
      {view.mode === "off" && !view.present && <p className="text-sm text-muted">{t("clientsOff")}</p>}
      {view.present ? (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="text-sm text-muted">{t(`types.${view.id_type ?? "il_id"}`)}</span>
          <span className="font-mono" dir="ltr" aria-live="polite">
            {revealed ?? maskedId(view.last4 ?? "")}
          </span>
          {view.can_reveal && (
            <button
              type="button"
              disabled={pending}
              className="btn-link text-sm text-primary-ink underline-offset-4 hover:underline"
              onClick={() =>
                revealed
                  ? setRevealed(null)
                  : startTransition(async () => {
                      const result = await revealIdentity(subject);
                      if (result.error) setError(t(`errors.${result.error}`));
                      else setRevealed(result.number ?? null);
                    })
              }
            >
              {revealed ? t("hide") : t("show")}
            </button>
          )}
        </div>
      ) : (
        manageable && <p className="text-sm text-muted">{t("none")}</p>
      )}
      {error && (
        <p role="alert" className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}
      {manageable && !editing && (
        <div className="flex flex-wrap gap-3">
          <button type="button" className="btn-secondary px-3 py-1.5 text-sm" onClick={() => setEditing(true)}>
            {view.present ? t("replace") : t("add")}
          </button>
          {view.present && (
            <button
              type="button"
              disabled={pending}
              className="btn-link text-sm text-danger underline-offset-4 hover:underline"
              onClick={async () => {
                if (!(await confirm({ message: t("removeConfirm"), confirmLabel: t("remove"), danger: true }))) return;
                startTransition(async () => apply(await removeIdentity(subject), () => setRevealed(null)));
              }}
            >
              {t("remove")}
            </button>
          )}
        </div>
      )}
      {manageable && editing && (
        <form onSubmit={submit} className="flex flex-col gap-3">
          <SelectField
            label={t("type")}
            value={idType}
            onChange={(event) => setIdType(event.target.value as IdType)}
            options={(["il_id", "passport", "foreign"] as const).map((value) => ({ value, label: t(`types.${value}`) }))}
          />
          <Field
            label={t("number")}
            value={number}
            onChange={(event) => setNumber(event.target.value)}
            inputMode={idType === "il_id" ? "numeric" : "text"}
            autoComplete="off"
            maxLength={idType === "il_id" ? 11 : 24}
            dir="ltr"
            required
          />
          {idType !== "il_id" && (
            <Field
              label={t("country")}
              hint={t("countryHint")}
              value={country}
              onChange={(event) => setCountry(event.target.value.toUpperCase())}
              maxLength={2}
              autoComplete="off"
              dir="ltr"
              required
            />
          )}
          <div className="flex gap-3">
            <button type="submit" disabled={pending} aria-busy={pending} className="btn-primary px-3 py-1.5 text-sm">
              {t("save")}
            </button>
            <button type="button" className="btn-ghost px-3 py-1.5 text-sm" onClick={() => setEditing(false)}>
              {t("cancel")}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
