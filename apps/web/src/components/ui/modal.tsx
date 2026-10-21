"use client";

import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import { type ReactNode, useCallback, useId, useLayoutEffect, useRef, useState, ViewTransition } from "react";

const CLOSE_MS = 150; // matches `.modal-dialog[data-closing]` in globals.css

/** The one window of the product: always centered with room around it (a sheet from the bottom on a
 * phone, or along the end edge with `placement="side"`). The page behind stays visible and blurred,
 * and does not scroll. Esc, the X and a click on the backdrop close it; with `dirty`
 * they first ask "Leave without saving?". Focus moves in and returns to the button that opened it
 * (native `<dialog>`; mark a button `data-autofocus` to start on it). Put the save and cancel buttons in `footer`: it stays visible without scrolling.
 * Mount it only while it is open, or pass `open`. With `transitionName` the window grows out of the
 * card that has the same name (see `CardTransition`) and shrinks back into it. */
export function Modal({
  open = true,
  onClose,
  title,
  description,
  children,
  footer,
  dirty = false,
  size = "lg",
  placement = "center",
  transitionName,
}: {
  open?: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  /** True while the form holds changes that are not saved yet. */
  dirty?: boolean;
  size?: "sm" | "md" | "lg";
  /** `side`: a sheet along the end edge that keeps a list in view (a full-screen sheet on a phone). */
  placement?: "center" | "side";
  /** The name of the card this window grows out of (a view transition shared element). */
  transitionName?: string;
}) {
  const t = useTranslations("common");
  const dialog = useRef<HTMLDialogElement>(null);
  const timer = useRef<number | undefined>(undefined);
  const titleId = useId();
  const descriptionId = useId();
  const [closing, setClosing] = useState(false);
  const [asking, setAsking] = useState(false);

  // A layout effect, so the window is on screen in the same commit as the navigation and the
  // browser can pair it with the card it grows out of.
  useLayoutEffect(() => {
    const element = dialog.current;
    if (!open || !element) return;
    if (!element.open) {
      element.showModal();
      // The browser focuses the first control (the X); a window may name a better one.
      element.querySelector<HTMLElement>("[data-autofocus]")?.focus({ preventScroll: true });
    }
    return () => {
      window.clearTimeout(timer.current);
      if (element.open) element.close();
    };
  }, [open]);

  const finish = useCallback(() => {
    setAsking(false);
    window.clearTimeout(timer.current);
    // The shrink back into the card is the closing animation.
    if (transitionName) {
      onClose();
      return;
    }
    setClosing(true);
    timer.current = window.setTimeout(() => {
      setClosing(false);
      onClose();
    }, CLOSE_MS);
  }, [onClose, transitionName]);

  const requestClose = useCallback(() => {
    if (dirty) setAsking(true);
    else finish();
  }, [dirty, finish]);

  if (!open) return null;
  return (
    <dialog
      ref={dialog}
      className="modal-dialog"
      data-closing={closing || undefined}
      data-placement={placement === "side" ? "side" : undefined}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onCancel={(event) => {
        event.preventDefault();
        if (asking) setAsking(false);
        else requestClose();
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) requestClose();
      }}
    >
      <PanelTransition name={transitionName}>
      <div className="modal-panel" data-size={size} data-morph={transitionName ? "" : undefined}>
        <header className="flex items-start gap-3 border-b border-border px-5 py-4 sm:px-6">
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="text-lg font-bold leading-snug">
              {title}
            </h2>
            {description ? (
              <p id={descriptionId} className="mt-0.5 text-sm text-muted">
                {description}
              </p>
            ) : null}
          </div>
          <button type="button" className="btn-icon -me-2 -mt-1" aria-label={t("closeDialog")} onClick={requestClose}>
            <X aria-hidden="true" className="size-5" />
          </button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6">{children}</div>
        {footer ? (
          <footer className="flex flex-wrap items-center justify-end gap-3 border-t border-border bg-surface px-5 py-3 sm:px-6">
            {footer}
          </footer>
        ) : null}
        {asking ? (
          <div className="modal-ask" role="alertdialog" aria-modal="true" aria-labelledby={`${titleId}-ask`}>
            <div className="card flex max-w-sm flex-col gap-4 p-6">
              <div>
                <h3 id={`${titleId}-ask`} className="font-bold">
                  {t("discardTitle")}
                </h3>
                <p className="mt-1 text-sm text-muted">{t("discardBody")}</p>
              </div>
              <div className="flex flex-wrap justify-end gap-3">
                <button type="button" className="btn-secondary px-4 py-2" autoFocus onClick={() => setAsking(false)}>
                  {t("keepEditing")}
                </button>
                <button type="button" className="btn-danger px-4 py-2" onClick={finish}>
                  {t("discard")}
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
      </PanelTransition>
    </dialog>
  );
}

function PanelTransition({ name, children }: { name?: string; children: ReactNode }) {
  if (!name) return children;
  return (
    <ViewTransition name={name} share="card-window" default="none">
      {children}
    </ViewTransition>
  );
}
