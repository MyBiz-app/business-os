"use client";

import { useFormStatus } from "react-dom";

export function SubmitButton({ children }: { children: React.ReactNode }) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      aria-busy={pending}
      className="rounded-lg bg-primary px-4 py-2.5 font-semibold text-white disabled:opacity-60 dark:text-background"
    >
      {children}
    </button>
  );
}
