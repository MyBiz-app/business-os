"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ReactNode, useEffect } from "react";

import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import { ModalMarker } from "@/components/ui/route-modal";
import { useToast } from "@/components/toast/toaster";
import type { FormState } from "@/lib/form-state";

/** One catalog form. In a window (`RouteModal` around it) a save closes the window; as a page a
 * new item goes back to the list and an edit stays put. Either way a save that closes shows a toast
 * and the list behind it refreshes. The save row stays visible while the fields scroll. */
export function CatalogFormFrame({
  modal,
  backHref,
  formAction,
  state,
  savedMessage,
  closeOnSave,
  readOnly = false,
  submitLabel,
  children,
  aside,
}: {
  modal: boolean;
  /** The list this form belongs to: where Cancel and a finished save lead when it is a page. */
  backHref: string;
  formAction: (formData: FormData) => void;
  state: FormState;
  savedMessage: string;
  closeOnSave: boolean;
  readOnly?: boolean;
  submitLabel: string;
  children: ReactNode;
  /** Shown under the fields, inside the form (rooms, a delete button). It must not hold another form. */
  aside?: ReactNode;
}) {
  const t = useTranslations("common");
  const router = useRouter();
  const toast = useToast();

  useEffect(() => {
    if (!state.saved || !closeOnSave) return;
    toast("success", savedMessage);
    // A window closes through ModalMarker; a page goes back to the list.
    if (!modal) router.push(backHref);
    router.refresh();
  }, [state, closeOnSave, modal, savedMessage, backHref, router, toast]);

  return (
    <form action={formAction} className="flex flex-col gap-4">
      <ModalMarker saved={closeOnSave && state.saved} />
      {/* A save that closes shows its own toast, so the form only reports errors then. */}
      <FormFeedback state={closeOnSave ? { error: state.error } : state} />
      {children}
      {aside}
      {!readOnly && (
        <div className="form-actions flex items-center gap-4">
          <SubmitButton>{submitLabel}</SubmitButton>
          {modal ? null : (
            <Link href={backHref} className="text-sm text-muted underline-offset-4 hover:underline">
              {t("cancel")}
            </Link>
          )}
        </div>
      )}
    </form>
  );
}
