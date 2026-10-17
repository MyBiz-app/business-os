"use client";

import { useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";

import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/toast/toaster";
import type { FormState } from "@/lib/form-state";

/** One catalog form, shown either as a window over the list (`modal`, reached by clicking in the
 * list) or as a normal page (a shared link, a refresh). The fields are the same in both. A save
 * closes the window (or goes back to the list) with a toast; an edit page that is not a window
 * stays put, as before. */
export function CatalogFormFrame({
  modal,
  title,
  description,
  backHref,
  formAction,
  state,
  savedMessage,
  closeOnSave,
  readOnly = false,
  submitLabel,
  size = "md",
  children,
  aside,
}: {
  modal: boolean;
  title: string;
  description?: string;
  /** The list this form belongs to: where Cancel and a finished save lead when it is a page. */
  backHref: string;
  formAction: (formData: FormData) => void;
  state: FormState;
  savedMessage: string;
  closeOnSave: boolean;
  readOnly?: boolean;
  submitLabel: string;
  size?: "sm" | "md" | "lg";
  children: ReactNode;
  /** Shown under the fields, inside the form (rooms, a delete button). It must not hold another form. */
  aside?: ReactNode;
}) {
  const t = useTranslations("common");
  const router = useRouter();
  const toast = useToast();
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (!state.saved) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDirty(false);
    if (!closeOnSave) return;
    toast("success", savedMessage);
    if (modal) router.back();
    else router.push(backHref);
    router.refresh();
  }, [state, closeOnSave, modal, savedMessage, backHref, router, toast]);

  // A save that closes the window shows its own toast, so the form only reports errors.
  const feedback = <FormFeedback state={closeOnSave ? { error: state.error } : state} />;

  if (modal) {
    return (
      <Modal
        title={title}
        description={description}
        size={size}
        dirty={dirty}
        onClose={() => router.back()}
        form={{ action: formAction, onChange: () => setDirty(true) }}
        cancelLabel={readOnly ? t("close") : t("cancel")}
        footer={readOnly ? undefined : <SubmitButton>{submitLabel}</SubmitButton>}
      >
        <div className="flex flex-col gap-4">
          {feedback}
          {children}
          {aside}
        </div>
      </Modal>
    );
  }
  return (
    <>
      <form action={formAction} className="flex flex-col gap-4">
        {feedback}
        {children}
        {!readOnly && (
          <div className="flex items-center gap-4">
            <SubmitButton>{submitLabel}</SubmitButton>
            <Link href={backHref} className="text-sm text-muted underline-offset-4 hover:underline">
              {t("cancel")}
            </Link>
          </div>
        )}
        {aside}
      </form>
    </>
  );
}
