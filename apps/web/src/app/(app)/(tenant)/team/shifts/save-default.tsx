"use client";

import { Bookmark } from "lucide-react";
import { useTranslations } from "next-intl";
import { useActionState } from "react";

import { type DefaultViewState, saveShiftsDefault } from "./actions";
import { FormError, FormNotice } from "@/components/form/form-message";

/** Owners: keeps the current view, range and branches as the way the shifts board opens. */
export function SaveShiftsDefault({ view, range, branches }: { view: "people" | "branches"; range: "day" | "week" | "month" | "custom"; branches: string[] }) {
  const t = useTranslations("shifts");
  const [state, action, pending] = useActionState<DefaultViewState, FormData>(saveShiftsDefault.bind(null, view, range, branches), {});

  return (
    <form action={action} className="flex items-center gap-2">
      <button type="submit" disabled={pending} aria-busy={pending} title={t("saveDefaultHint")} className="btn-ghost gap-1.5 px-3 py-1.5 text-sm">
        <Bookmark aria-hidden="true" className="size-4" />
        {t("saveDefault")}
      </button>
      <FormNotice message={state.saved ? t("defaultSaved") : undefined} />
      <FormError toastOnly message={state.error ? t("defaultError") : undefined} />
    </form>
  );
}
