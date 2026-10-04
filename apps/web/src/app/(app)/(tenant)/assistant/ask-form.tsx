"use client";

import { useTranslations } from "next-intl";
import { useActionState, useRef } from "react";
import { useFormStatus } from "react-dom";

import { FormError } from "@/components/form/form-message";

import type { AskState } from "./actions";

function SendButton() {
  const t = useTranslations("assistant");
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      aria-busy={pending}
      className="btn-primary px-4 py-2.5"
    >
      {pending ? t("thinking") : t("send")}
    </button>
  );
}

function Pending() {
  const t = useTranslations("assistant");
  const { pending, data } = useFormStatus();
  if (!pending) return null;
  return (
    <div className="flex flex-col gap-2" aria-live="polite">
      <p className="self-end whitespace-pre-wrap rounded-2xl bg-primary px-4 py-2.5 text-on-primary" dir="auto">
        {String(data?.get("text") ?? "")}
      </p>
      <p className="animate-pulse text-sm text-muted">{t("thinking")}</p>
    </div>
  );
}

type Props = { action: (state: AskState, formData: FormData) => Promise<AskState>; suggestions: string[] };

export function AskForm({ action, suggestions }: Props) {
  const t = useTranslations("assistant");
  const [state, formAction] = useActionState(action, {});
  const form = useRef<HTMLFormElement>(null);

  return (
    <form
      ref={form}
      action={async (formData) => {
        form.current?.reset();
        await formAction(formData);
      }}
      className="flex flex-col gap-3"
    >
      <Pending />
      <FormError message={state.error && t(`errors.${state.error}`)} />
      <div className="flex flex-wrap gap-2">
        {suggestions.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => {
              const input = form.current?.elements.namedItem("text") as HTMLTextAreaElement | null;
              if (input) {
                input.value = suggestion;
                form.current?.requestSubmit();
              }
            }}
            className="rounded-full border border-border px-3 py-1 text-sm hover:bg-surface"
          >
            {suggestion}
          </button>
        ))}
      </div>
      <div className="flex items-end gap-2">
        <label htmlFor="assistant-question" className="sr-only">
          {t("question")}
        </label>
        <textarea
          id="assistant-question"
          name="text"
          required
          rows={2}
          maxLength={4000}
          dir="auto"
          placeholder={t("placeholder")}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              form.current?.requestSubmit();
            }
          }}
          className="min-w-0 flex-1 resize-none control px-3 py-2"
        />
        <SendButton />
      </div>
    </form>
  );
}
