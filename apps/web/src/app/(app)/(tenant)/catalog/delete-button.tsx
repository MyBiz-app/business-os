"use client";

import { Trash2 } from "lucide-react";

import { useConfirm } from "@/components/ui/confirm-dialog";

/** A delete button that asks first. It lives inside the edit form and submits to its own action
 * (a form cannot sit inside another form), so it needs no fields to be valid. */
export function DeleteButton({ action, label, confirm }: { action: () => Promise<void>; label: string; confirm: string }) {
  const ask = useConfirm();
  return (
    <div className="border-t border-border pt-4">
      <button
        type="submit"
        formAction={action}
        formNoValidate
        onClick={(event) => {
          // Held back while the question is open; a "yes" submits the form through this same button.
          event.preventDefault();
          const button = event.currentTarget;
          void ask({ message: confirm, confirmLabel: label, danger: true }).then((yes) => {
            if (yes) button.form?.requestSubmit(button);
          });
        }}
        className="btn-link inline-flex items-center gap-1.5 text-sm text-danger underline-offset-4 hover:underline"
      >
        <Trash2 aria-hidden="true" className="size-4" />
        {label}
      </button>
    </div>
  );
}
