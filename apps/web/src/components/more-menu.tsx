"use client";

import { ChevronDown } from "lucide-react";
import { type ReactNode, useCallback, useId, useRef, useState } from "react";

import { useDismiss } from "@/components/use-dismiss";

/** A secondary-actions button that opens a small panel under it (for a page header with one main action). */
export function MoreMenu({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const panel = useId();
  const close = useCallback(() => setOpen(false), []);
  useDismiss(open, close, root, button);

  return (
    <div ref={root} className="relative">
      <button ref={button} type="button" aria-expanded={open} aria-controls={panel} onClick={() => setOpen((value) => !value)} className="btn-secondary gap-1.5 px-4 py-2.5 text-sm">
        {label}
        <ChevronDown aria-hidden="true" className={`size-4 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      <div id={panel} data-open={open} className="popover absolute end-0 top-full z-40 mt-2 flex w-64 origin-top-right flex-col gap-1 p-2 rtl:origin-top-left">
        {children}
      </div>
    </div>
  );
}
