"use client";

import { Check, LoaderCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { useFormStatus } from "react-dom";

import { FORM_SAVED_EVENT } from "./form-message";

type Props = {
  children: React.ReactNode;
  disabled?: boolean;
  /** `secondary` for a second action in the same form; defaults to the main action. */
  variant?: "primary" | "secondary" | "danger";
  className?: string;
};

/** A form's submit button: shows a spinner while the form is saving and cannot be pressed twice. */
export function SubmitButton({ children, disabled = false, variant = "primary", className = "px-4 py-2.5" }: Props) {
  const { pending } = useFormStatus();
  const t = useTranslations("common");
  const button = useRef<HTMLButtonElement>(null);
  const [saved, setSaved] = useState(false);
  // A form that saves ends with FormNotice: the button itself turns into "Saved" for a moment.
  useEffect(() => {
    const form = button.current?.form;
    if (!form) return;
    let timer: number | undefined;
    const onSaved = () => {
      setSaved(true);
      window.clearTimeout(timer);
      timer = window.setTimeout(() => setSaved(false), 1600);
    };
    form.addEventListener(FORM_SAVED_EVENT, onSaved);
    return () => {
      form.removeEventListener(FORM_SAVED_EVENT, onSaved);
      window.clearTimeout(timer);
    };
  }, []);
  const hidden = pending || saved;
  return (
    <button ref={button} type="submit" disabled={pending || disabled} aria-busy={pending} className={`btn-plain btn-${variant} relative ${className}`}>
      <span className={`inline-flex items-center gap-2 ${hidden ? "invisible" : ""}`}>{children}</span>
      {pending && <LoaderCircle aria-hidden="true" className="absolute size-4 animate-spin motion-reduce:animate-none" />}
      {saved && !pending && (
        <span className="absolute inline-flex items-center gap-1.5">
          <Check aria-hidden="true" className="size-4" />
          {t("savedShort")}
        </span>
      )}
    </button>
  );
}
