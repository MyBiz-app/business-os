"use client";

import { AlertCircle, ArrowBigUp, Eye, EyeOff } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState } from "react";

type PasswordFieldProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> & {
  label: string;
  hint?: string;
  /** A problem with this password (wrong, too weak): shown right under the field, which turns red. */
  error?: string;
};

/** A password input with a show/hide button (always left to right, like any secret). The icon shows
 * what the field is now: an open eye while the password is visible, a crossed eye while it is hidden.
 * A notice appears while Caps Lock is on, before the first wrong try. */
export function PasswordField({ label, hint, error, onKeyDown, onKeyUp, onBlur, ...inputProps }: PasswordFieldProps) {
  const t = useTranslations("auth");
  const id = useId();
  const hintId = hint && !error ? `${id}-hint` : undefined;
  const input = useRef<HTMLInputElement>(null);
  const errorId = error ? `${id}-error` : undefined;
  const capsId = `${id}-caps`;
  const [visible, setVisible] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  // A new problem sends the cursor back to the field to try again (the form emptied it).
  useEffect(() => {
    if (error) input.current?.focus();
  }, [error]);
  const toggle = visible ? t("hidePassword") : t("showPassword");
  const track = (event: React.KeyboardEvent<HTMLInputElement>) => {
    // Some keyboards report no state for a bare modifier key; leave the last known state then.
    if (typeof event.getModifierState === "function") setCapsLock(event.getModifierState("CapsLock"));
  };
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <div dir="ltr" className="relative">
        <input
          ref={input}
          id={id}
          aria-describedby={[hintId, capsLock ? capsId : undefined, errorId].filter(Boolean).join(" ") || undefined}
          aria-invalid={error ? true : undefined}
          className="control w-full min-w-0 py-2 ps-3 pe-11"
          dir="ltr"
          {...inputProps}
          type={visible ? "text" : "password"}
          onKeyDown={(event) => {
            track(event);
            onKeyDown?.(event);
          }}
          onKeyUp={(event) => {
            track(event);
            onKeyUp?.(event);
          }}
          onBlur={(event) => {
            setCapsLock(false);
            onBlur?.(event);
          }}
        />
        <button
          type="button"
          aria-label={toggle}
          aria-pressed={visible}
          title={toggle}
          onClick={() => setVisible((v) => !v)}
          className="btn-plain absolute inset-y-0 end-0 flex w-10 items-center justify-center text-muted hover:text-foreground"
        >
          {visible ? <Eye aria-hidden="true" className="size-4" /> : <EyeOff aria-hidden="true" className="size-4" />}
        </button>
      </div>
      {capsLock && (
        <p id={capsId} role="status" className="flex items-center gap-1.5 text-xs font-medium text-warning">
          <ArrowBigUp aria-hidden="true" className="size-4 shrink-0" />
          {t("capsLockOn")}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="field-error flex items-start gap-1.5 text-sm text-danger">
          <AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          {error}
        </p>
      )}
      {hint && !error && (
        <p id={hintId} className="text-xs text-muted">
          {hint}
        </p>
      )}
    </div>
  );
}
