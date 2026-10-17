"use client";

import { Eye, EyeOff } from "lucide-react";
import { useTranslations } from "next-intl";
import { useId, useState } from "react";

type PasswordFieldProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> & {
  label: string;
  hint?: string;
};

/** A password input with a show/hide button (always left to right, like any secret). */
export function PasswordField({ label, hint, ...inputProps }: PasswordFieldProps) {
  const t = useTranslations("auth");
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const [visible, setVisible] = useState(false);
  const toggle = visible ? t("hidePassword") : t("showPassword");
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <div dir="ltr" className="relative">
        <input
          id={id}
          aria-describedby={hintId}
          className="control w-full min-w-0 py-2 ps-3 pe-11"
          dir="ltr"
          {...inputProps}
          type={visible ? "text" : "password"}
        />
        <button
          type="button"
          aria-label={toggle}
          aria-pressed={visible}
          title={toggle}
          onClick={() => setVisible((v) => !v)}
          className="btn-plain absolute inset-y-0 end-0 flex w-10 items-center justify-center text-muted hover:text-foreground"
        >
          {visible ? <EyeOff aria-hidden="true" className="size-4" /> : <Eye aria-hidden="true" className="size-4" />}
        </button>
      </div>
      {hint && (
        <p id={hintId} className="text-xs text-muted">
          {hint}
        </p>
      )}
    </div>
  );
}
