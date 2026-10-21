"use client";

import { useTranslations } from "next-intl";
import { createContext, type FormEvent, type ReactNode, useCallback, useContext, useRef, useState } from "react";

import { Modal } from "@/components/ui/modal";

export type ConfirmOptions = {
  /** The question. */
  message: string;
  /** A short heading above it; "Are you sure?" when left out. */
  title?: string;
  /** The label of the action button; "Confirm" when left out. */
  confirmLabel?: string;
  /** A destructive action gets a red button, and "Cancel" stays the one in focus. */
  danger?: boolean;
};

/** A question in the product's own window, instead of the browser's grey box. Cancel has the focus,
 * so an Enter by mistake never deletes anything. Esc, the X and the dimmed page also cancel. */
export function ConfirmDialog({
  open = true,
  onConfirm,
  onCancel,
  message,
  title,
  confirmLabel,
  danger = false,
}: ConfirmOptions & { open?: boolean; onConfirm: () => void; onCancel: () => void }) {
  const t = useTranslations("common");
  return (
    <Modal
      open={open}
      onClose={onCancel}
      size="sm"
      title={title ?? t("confirmTitle")}
      footer={
        <>
          <button type="button" className="btn-secondary px-4 py-2 text-sm" data-autofocus onClick={onCancel}>
            {t("cancel")}
          </button>
          <button type="button" className={`${danger ? "btn-danger" : "btn-primary"} px-4 py-2 text-sm`} onClick={onConfirm}>
            {confirmLabel ?? t("confirmAction")}
          </button>
        </>
      }
    >
      <p className="text-sm leading-relaxed" dir="auto">
        {message}
      </p>
    </Modal>
  );
}

type Ask = (options: ConfirmOptions) => Promise<boolean>;
const ConfirmContext = createContext<Ask | null>(null);

/** Gives every screen below it `useConfirm()`. Mounted once, in the app layout. */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<{ options: ConfirmOptions; resolve: (answer: boolean) => void } | null>(null);
  const ask = useCallback<Ask>((options) => new Promise<boolean>((resolve) => setPending({ options, resolve })), []);
  const answer = (value: boolean) => {
    pending?.resolve(value);
    setPending(null);
  };
  return (
    <ConfirmContext value={ask}>
      {children}
      {pending ? <ConfirmDialog {...pending.options} onConfirm={() => answer(true)} onCancel={() => answer(false)} /> : null}
    </ConfirmContext>
  );
}

/** `if (!(await confirm({ message, danger: true }))) return;` */
export function useConfirm(): Ask {
  const ask = useContext(ConfirmContext);
  if (!ask) throw new Error("useConfirm needs a ConfirmProvider above it");
  return ask;
}

/** For a form that must ask before it is sent: `<form action={…} onSubmit={onSubmit}>`. The first
 * submit is held back and asked about; a "yes" sends the form again. */
export function useConfirmedSubmit({ message, title, confirmLabel, danger }: ConfirmOptions): (event: FormEvent<HTMLFormElement>) => void {
  const confirm = useConfirm();
  const approved = useRef(false);
  return useCallback(
    (event) => {
      if (approved.current) {
        approved.current = false;
        return;
      }
      event.preventDefault();
      const form = event.currentTarget;
      void confirm({ message, title, confirmLabel, danger }).then((yes) => {
        if (!yes) return;
        approved.current = true;
        form.requestSubmit();
      });
    },
    [confirm, message, title, confirmLabel, danger],
  );
}
