"use client";

import { Trash2 } from "lucide-react";

import { useConfirmedSubmit } from "@/components/ui/confirm-dialog";

/** A delete button that asks first. Render it only for people allowed to delete. */
export function ConfirmDelete({ action, label, confirm }: { action: () => Promise<void>; label: string; confirm: string }) {
  const onSubmit = useConfirmedSubmit({ message: confirm, confirmLabel: label, danger: true });
  return (
    <form action={action} onSubmit={onSubmit}>
      <button type="submit" className="btn-link inline-flex items-center gap-1.5 text-sm text-danger underline-offset-4 hover:underline">
        <Trash2 aria-hidden="true" className="size-4" />
        {label}
      </button>
    </form>
  );
}
