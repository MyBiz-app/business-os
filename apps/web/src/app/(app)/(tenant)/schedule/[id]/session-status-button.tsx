"use client";

import { useTransition } from "react";
import { Button } from "@/components/ui/button";

import { useToast } from "@/components/toast/toaster";

import { setSessionStatus } from "../actions";

/** Cancels a session (or brings it back), with a toast whose "Undo" reverses it. */
export function SessionStatusButton({
  sessionId,
  cancelled,
  labels,
}: {
  sessionId: string;
  cancelled: boolean;
  labels: { cancel: string; restore: string; cancelled: string; restored: string; undo: string };
}) {
  const toast = useToast();
  const [pending, startTransition] = useTransition();

  function run(cancel: boolean) {
    startTransition(async () => {
      await setSessionStatus(sessionId, cancel ? "cancelled" : "scheduled");
      toast("success", cancel ? labels.cancelled : labels.restored, { action: { label: labels.undo, onClick: () => run(!cancel) } });
    });
  }

  return (
    <Button
      variant="plain"
      disabled={pending}
      className={`btn-link text-sm underline-offset-4 hover:underline ${cancelled ? "text-primary-ink" : "text-danger"}`}
      onClick={() => run(!cancelled)}
    >
      {cancelled ? labels.restore : labels.cancel}
    </Button>
  );
}
