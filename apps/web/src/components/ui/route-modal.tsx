"use client";

import { useRouter } from "next/navigation";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { Modal } from "./modal";

type RouteModalValue = {
  /** Closes the window without asking about unsaved changes. `next` replaces it with that page. */
  finish: (next?: string) => void;
};

const RouteModalContext = createContext<RouteModalValue | null>(null);

/** A page shown as a window over the page behind it (an intercepted route in the `@modal` slot).
 * Closing goes back one step in the history; the same address opened directly is a normal page.
 * Typing in any field marks the window as holding unsaved changes. */
export function RouteModal({
  title,
  description,
  size,
  transitionName,
  children,
}: {
  title: string;
  description?: string;
  size?: "sm" | "md" | "lg";
  /** The card in the list behind that this window grows out of; pair it with `CardTransition`. */
  transitionName?: string;
  children: ReactNode;
}) {
  const router = useRouter();
  const [dirty, setDirty] = useState(false);
  const close = useCallback(() => router.back(), [router]);
  const finish = useCallback(
    (next?: string) => {
      setDirty(false);
      if (next) router.replace(next);
      else router.back();
    },
    [router],
  );
  const value = useMemo(() => ({ finish }), [finish]);

  return (
    <RouteModalContext.Provider value={value}>
      <Modal title={title} description={description} size={size} transitionName={transitionName} dirty={dirty} onClose={close}>
        <div onInput={() => setDirty(true)} onChange={() => setDirty(true)}>
          {children}
        </div>
      </Modal>
    </RouteModalContext.Provider>
  );
}

/** Put inside a form: in a window it tells the save action not to redirect (`_modal`) and closes
 * the window once the form reports `saved`, going to `next` when the action says where. Outside a
 * window it renders nothing and does nothing. */
export function ModalMarker({ saved, next }: { saved?: boolean; next?: string }) {
  const modal = useContext(RouteModalContext);
  const finish = modal?.finish;
  useEffect(() => {
    if (saved) finish?.(next);
  }, [saved, next, finish]);
  return modal ? <input type="hidden" name="_modal" value="1" /> : null;
}
