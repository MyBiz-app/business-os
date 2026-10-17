"use client";

import { AlertCircle, Check, Info, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import "./toast.css";

export type ToastTone = "success" | "error" | "info";
/** An optional button in the toast: "Undo" after a delete, "View" after a create, "Try again" after an error. */
export type ToastAction = { label: string; onClick?: () => void; href?: string };
export type ToastOptions = { action?: ToastAction };
type ToastItem = { id: number; tone: ToastTone; message: string; action?: ToastAction; leaving?: boolean };

/** Errors have no timer: they stay until closed. */
const DURATION_MS: Record<ToastTone, number | null> = { success: 5000, info: 5000, error: null };
const MAX_VISIBLE = 3;
const LEAVE_MS = 180;

type ShowToast = (tone: ToastTone, message: string, options?: ToastOptions) => void;
const ToastContext = createContext<ShowToast>(() => {});

/** Shows a toast: `const toast = useToast(); toast("success", "Saved.")`. Forms get this for free
 * through FormNotice and FormError. */
export function useToast() {
  return useContext(ToastContext);
}

/** Mounted once in the root layout. Toasts sit in the browser's top layer (a popover), so they
 * show above dialogs and stay at the bottom of the screen wherever the page is scrolled. */
export function Toaster({ children }: { children: React.ReactNode }) {
  const t = useTranslations("common");
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);
  const timers = useRef(new Map<number, number>());
  const layer = useRef<HTMLDivElement>(null);

  const remove = useCallback((id: number) => {
    window.clearTimeout(timers.current.get(id));
    timers.current.delete(id);
    setItems((all) => all.map((item) => (item.id === id ? { ...item, leaving: true } : item)));
    window.setTimeout(() => setItems((all) => all.filter((item) => item.id !== id)), LEAVE_MS);
  }, []);

  const push = useCallback(
    (tone: ToastTone, message: string, options?: ToastOptions) => {
      const id = nextId.current++;
      setItems((all) => {
        // The same message again replaces the old one, so it restarts instead of piling up.
        const rest = all.filter((item) => !(item.tone === tone && item.message === message && !item.leaving));
        return [...rest, { id, tone, message, action: options?.action }].slice(-MAX_VISIBLE);
      });
      const ms = DURATION_MS[tone];
      if (ms !== null) timers.current.set(id, window.setTimeout(() => remove(id), ms));
    },
    [remove],
  );

  useEffect(() => {
    const running = timers.current;
    return () => running.forEach((timer) => window.clearTimeout(timer));
  }, []);

  // Open the popover layer while there is something to show; re-open it on each new toast so it
  // lands above a dialog opened since.
  useEffect(() => {
    const element = layer.current;
    if (!element || typeof element.showPopover !== "function") return;
    if (items.length === 0) {
      if (element.matches(":popover-open")) element.hidePopover();
      return;
    }
    if (element.matches(":popover-open")) element.hidePopover();
    element.showPopover();
  }, [items.length, items[items.length - 1]?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const pause = (id: number) => {
    window.clearTimeout(timers.current.get(id));
    timers.current.delete(id);
  };
  const resume = (item: ToastItem) => {
    if (timers.current.has(item.id) || item.leaving || DURATION_MS[item.tone] === null) return;
    timers.current.set(item.id, window.setTimeout(() => remove(item.id), 2500));
  };

  const api = useMemo<ShowToast>(() => push, [push]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div ref={layer} popover="manual" className="toaster" aria-label={t("notifications")} data-count={items.length}>
        <div className="toaster-pile">
        {items.map((item, index) => {
          const ms = DURATION_MS[item.tone];
          return (
            <div
              key={item.id}
              className="toast"
              data-tone={item.tone}
              data-leaving={item.leaving ? "true" : undefined}
              role={item.tone === "error" ? "alert" : "status"}
              style={{ "--toast-depth": items.length - 1 - index, ...(ms !== null ? { "--toast-ms": `${ms}ms` } : {}) } as React.CSSProperties}
              onMouseEnter={() => pause(item.id)}
              onMouseLeave={() => resume(item)}
              onFocus={() => pause(item.id)}
              onBlur={() => resume(item)}
            >
              <span aria-hidden="true" className="toast-icon">
                {item.tone === "error" ? <AlertCircle className="size-3.5" strokeWidth={3} /> : item.tone === "info" ? <Info className="size-3.5" strokeWidth={3} /> : <Check className="size-3.5" strokeWidth={3} />}
              </span>
              <p className="toast-message">{item.message}</p>
              {item.action ? (
                item.action.href ? (
                  <a href={item.action.href} className="toast-action" onClick={() => remove(item.id)}>
                    {item.action.label}
                  </a>
                ) : (
                  <button
                    type="button"
                    className="btn-plain toast-action"
                    onClick={() => {
                      item.action?.onClick?.();
                      remove(item.id);
                    }}
                  >
                    {item.action.label}
                  </button>
                )
              ) : null}
              <button type="button" className="btn-plain toast-close" aria-label={t("dismiss")} onClick={() => remove(item.id)}>
                <X aria-hidden="true" className="size-4" />
              </button>
              {ms !== null ? <span aria-hidden="true" className="toast-bar" /> : null}
            </div>
          );
        })}
        </div>
      </div>
    </ToastContext.Provider>
  );
}

/** For results kept in state without a form action (a transition, a fetch): shows the message
 * each time `source` changes to a new result, even when the text is the same as last time. */
export function ToastOnChange({ source, tone, message, action }: { source: unknown; tone: ToastTone; message?: string; action?: ToastAction }) {
  const toast = useToast();
  useEffect(() => {
    if (message) toast(tone, message, action ? { action } : undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source]);
  return null;
}
