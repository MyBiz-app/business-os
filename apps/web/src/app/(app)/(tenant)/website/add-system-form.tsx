"use client";

import { useActionState } from "react";

import { FormFeedback } from "@/components/form/form-feedback";
import { SubmitButton } from "@/components/form/submit-button";

import { addSystem } from "./actions";

/** "Add the system": one button; the business keeps its account and gets its modules. */
export function AddSystemForm({ label }: { label: string }) {
  const [state, action] = useActionState(addSystem, {});
  return (
    <form action={action} className="flex flex-col gap-3">
      <FormFeedback state={state} />
      <div>
        <SubmitButton>{label}</SubmitButton>
      </div>
    </form>
  );
}
