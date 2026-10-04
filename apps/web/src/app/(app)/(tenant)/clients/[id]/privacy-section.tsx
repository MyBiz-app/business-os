"use client";

import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { CheckboxField } from "@/components/form/field";
import { FormError } from "@/components/form/form-message";

import { eraseClient, type EraseState } from "./privacy-actions";

/** Privacy requests (owners): download the client's data, or erase their personal details. */
export function PrivacySection({ clientId, name }: { clientId: string; name: string }) {
  const t = useTranslations("privacy");
  const [state, action, pending] = useActionState<EraseState, FormData>(eraseClient.bind(null, clientId), {});

  return (
    <section aria-labelledby="privacy-heading" className="flex flex-col gap-4 card p-6">
      <div className="flex flex-col gap-1">
        <h2 id="privacy-heading" className="text-lg font-semibold">
          {t("title")}
        </h2>
        <p className="text-sm text-muted">{t("intro")}</p>
      </div>
      <div>
        <a
          href={`/clients/${clientId}/export`}
          download
          className="btn-secondary px-4 py-2.5"
        >
          {t("export")}
        </a>
      </div>
      <details className="border-t border-border pt-4">
        <summary className="cursor-pointer font-semibold text-danger">{t("erase")}</summary>
        <form action={action} className="mt-3 flex flex-col gap-3">
          <p className="text-sm">{t("eraseExplain")}</p>
          <FormError message={state.error && t(`errors.${state.error}`)} />
          <CheckboxField label={t("eraseConfirm", { name })} name="confirm" />
          <div>
            <button
              type="submit"
              disabled={pending}
              aria-busy={pending}
              className="rounded-lg border border-danger px-4 py-2.5 font-semibold text-danger disabled:opacity-60"
            >
              {t("eraseButton")}
            </button>
          </div>
        </form>
      </details>
    </section>
  );
}
