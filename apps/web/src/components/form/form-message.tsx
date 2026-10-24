"use client";

import { BRAND } from "@business-os/i18n/brand";
import { AlertCircle } from "lucide-react";
import { useEffect, useRef } from "react";
import { useFormStatus } from "react-dom";

import { type ToastTone, useToast } from "@/components/toast/toaster";

/** Shows the message as a toast when a form finishes (or when the page opens with it), so it is
 * seen wherever the page is scrolled. Repeats when the same message comes back from a new submit. */
function useToastMessage(tone: ToastTone, message?: string, enabled = true) {
  const toast = useToast();
  const { pending } = useFormStatus();
  useEffect(() => {
    if (enabled && message && !pending) toast(tone, message);
  }, [message, pending, tone, toast, enabled]);
}

/** An error is also shown in the form, next to the fields, until the next try; `toastOnly` is for
 * small inline controls that have no room for it. `inline` is for short forms (sign-in, sign-up),
 * where the message is already in view: it stays in the form only, with no toast on top of it.
 * A problem with one field belongs under that field (see PasswordField's `error`), not here. */
export function FormError({ message, toastOnly, inline }: { message?: string; toastOnly?: boolean; inline?: boolean }) {
  useToastMessage("error", message, !inline);
  if (!message || toastOnly) return null;
  return (
    <p role="alert" className="field-error flex items-start gap-2 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
      <AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <span>{message}</span>
    </p>
  );
}

/** A confirmation, shown as a toast only. */
export function FormNotice({ message }: { message?: string }) {
  const marker = useRef<HTMLSpanElement>(null);
  const { pending } = useFormStatus();
  useToastMessage("success", message);
  // Tells the form's submit button, which turns into "Saved" for a moment.
  useEffect(() => {
    if (message && !pending) marker.current?.closest("form")?.dispatchEvent(new CustomEvent(FORM_SAVED_EVENT));
  }, [message, pending]);
  return <span ref={marker} hidden />;
}

export const FORM_SAVED_EVENT = `${BRAND.app.storagePrefix}:form-saved`;
