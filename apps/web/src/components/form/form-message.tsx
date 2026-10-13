"use client";

import { useEffect } from "react";
import { useFormStatus } from "react-dom";

import { type ToastTone, useToast } from "@/components/toast/toaster";

/** Shows the message as a toast when a form finishes (or when the page opens with it), so it is
 * seen wherever the page is scrolled. Repeats when the same message comes back from a new submit. */
function useToastMessage(tone: ToastTone, message?: string) {
  const toast = useToast();
  const { pending } = useFormStatus();
  useEffect(() => {
    if (message && !pending) toast(tone, message);
  }, [message, pending, tone, toast]);
}

/** An error is also shown in the form, next to the fields, until the next try; `toastOnly` is for
 * small inline controls that have no room for it. */
export function FormError({ message, toastOnly }: { message?: string; toastOnly?: boolean }) {
  useToastMessage("error", message);
  if (!message || toastOnly) return null;
  return <p className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">{message}</p>;
}

/** A confirmation, shown as a toast only. */
export function FormNotice({ message }: { message?: string }) {
  useToastMessage("success", message);
  return null;
}
