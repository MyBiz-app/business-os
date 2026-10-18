"use client";

import { Pause, Play, Trash2 } from "lucide-react";

/** Pause / resume and delete for one code. Two small forms side by side, so it works inside a
 * window footer and on a page. A code that was used cannot be deleted (only paused). */
export function PromoActions({
  active,
  deletable,
  toggle,
  remove,
  toggleLabel,
  deleteLabel,
  deleteConfirm,
}: {
  active: boolean;
  deletable: boolean;
  toggle: () => Promise<void>;
  remove: () => Promise<void>;
  toggleLabel: string;
  deleteLabel: string;
  deleteConfirm: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <form action={toggle}>
        <button type="submit" className="btn-secondary inline-flex items-center gap-1.5 px-4 py-2">
          {active ? <Pause aria-hidden="true" className="size-4" /> : <Play aria-hidden="true" className="size-4" />}
          {toggleLabel}
        </button>
      </form>
      {deletable && (
        <form
          action={remove}
          onSubmit={(event) => {
            if (!window.confirm(deleteConfirm)) event.preventDefault();
          }}
        >
          <button type="submit" className="btn-link inline-flex items-center gap-1.5 text-sm text-danger underline-offset-4 hover:underline">
            <Trash2 aria-hidden="true" className="size-4" />
            {deleteLabel}
          </button>
        </form>
      )}
    </div>
  );
}
