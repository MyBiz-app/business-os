"use client";

import { CircleAlert, CircleCheck, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import "./toast.css";

export type ToastTone = "success" | "error";
type ToastItem = { id: number; tone: ToastTone; message: string; leaving?: boolean };

const DURATION_MS: Record<ToastTone, number> = { success: 5000, error: 9000 };
const MAX_VISIBLE = 3;
const LEAVE_MS = 180;

const ToastContext = createContext<(tone: ToastTone, message: string) => void>(() => {});

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
    (tone: ToastTone, message: string) => {
      const id = nextId.current++;
      setItems((all) => {
        // The same message again replaces the old one, so it restarts instead of piling up.
        const rest = all.filter((item) => !(item.tone === tone && item.message === message && !item.leaving));
        return [...rest, { id, tone, message }].slice(-MAX_VISIBLE);
      });
      timers.current.set(id, window.setTimeout(() => remove(id), DURATION_MS[tone]));
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
    if (timers.current.has(item.id) || item.leaving) return;
    timers.current.set(item.id, window.setTimeout(() => remove(item.id), 2500));
  };

  const api = useMemo(() => push, [push]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div ref={layer} popover="manual" className="toaster">
        {items.map((item) => (
          <div
            key={item.id}
            className="toast"
            data-tone={item.tone}
            data-leaving={item.leaving ? "true" : undefined}
            role={item.tone === "error" ? "alert" : "status"}
            style={{ "--toast-ms": `${DURATION_MS[item.tone]}ms` } as React.CSSProperties}
            onMouseEnter={() => pause(item.id)}
            onMouseLeave={() => resume(item)}
            onFocus={() => pause(item.id)}
            onBlur={() => resume(item)}
          >
            {item.tone === "error" ? (
              <CircleAlert aria-hidden="true" className="toast-icon size-5" />
            ) : (
              <CircleCheck aria-hidden="true" className="toast-icon size-5" />
            )}
            <p className="toast-message">{item.message}</p>
            <button type="button" className="btn-plain toast-close" aria-label={t("dismiss")} onClick={() => remove(item.id)}>
              <X aria-hidden="true" className="size-4" />
            </button>
            <span aria-hidden="true" className="toast-bar" />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

/** For results kept in state without a form action (a transition, a fetch): shows the message
 * each time `source` changes to a new result, even when the text is the same as last time. */
export function ToastOnChange({ source, tone, message }: { source: unknown; tone: ToastTone; message?: string }) {
  const toast = useToast();
  useEffect(() => {
    if (message) toast(tone, message);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source]);
  return null;
}
