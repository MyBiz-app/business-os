"use client";

import { useFormStatus } from "react-dom";

export function SubmitButton({ children, disabled = false }: { children: React.ReactNode; disabled?: boolean }) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending || disabled}
      aria-busy={pending}
      className="btn-primary px-4 py-2.5"
    >
      {children}
    </button>
  );
}
