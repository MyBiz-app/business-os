"use client";

import { Archive, ArchiveRestore } from "lucide-react";
import { useTransition } from "react";

import { useToast } from "@/components/toast/toaster";

import { setArchived } from "./actions";

/** Archives a file (or brings it back) and says so in a toast with an "Undo" that reverses it,
 * instead of asking "are you sure?" for something that can be undone. */
export function ArchiveButton({
  fileId,
  name,
  archived,
  labels,
}: {
  fileId: string;
  name: string;
  /** True when the file is archived now (the button restores it). */
  archived: boolean;
  labels: { archive: string; restore: string; archived: string; restored: string; undo: string };
}) {
  const toast = useToast();
  const [pending, startTransition] = useTransition();

  function run(archive: boolean) {
    startTransition(async () => {
      await setArchived(fileId, archive);
      toast("success", archive ? labels.archived : labels.restored, { action: { label: labels.undo, onClick: () => run(!archive) } });
    });
  }

  return (
    <button type="button" className="btn-secondary px-2.5 py-1 text-xs" disabled={pending} aria-label={`${archived ? labels.restore : labels.archive}: ${name}`} onClick={() => run(!archived)}>
      {archived ? <ArchiveRestore aria-hidden="true" className="size-3.5" /> : <Archive aria-hidden="true" className="size-3.5" />}
      {archived ? labels.restore : labels.archive}
    </button>
  );
}
