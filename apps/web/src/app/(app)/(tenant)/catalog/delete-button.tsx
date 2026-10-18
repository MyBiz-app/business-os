"use client";

import { Trash2 } from "lucide-react";

/** A delete button that asks first. It lives inside the edit form and submits to its own action
 * (a form cannot sit inside another form), so it needs no fields to be valid. */
export function DeleteButton({ action, label, confirm }: { action: () => Promise<void>; label: string; confirm: string }) {
  return (
    <div className="border-t border-border pt-4">
      <button
        type="submit"
        formAction={action}
        formNoValidate
        onClick={(event) => {
          if (!window.confirm(confirm)) event.preventDefault();
        }}
        className="btn-link inline-flex items-center gap-1.5 text-sm text-danger underline-offset-4 hover:underline"
      >
        <Trash2 aria-hidden="true" className="size-4" />
        {label}
      </button>
    </div>
  );
}
