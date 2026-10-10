"use client";

import { LoaderCircle } from "lucide-react";
import { useFormStatus } from "react-dom";

type Props = {
  children: React.ReactNode;
  disabled?: boolean;
  /** `secondary` for a second action in the same form; defaults to the main action. */
  variant?: "primary" | "secondary" | "danger";
  className?: string;
};

/** A form's submit button: shows a spinner while the form is saving and cannot be pressed twice. */
export function SubmitButton({ children, disabled = false, variant = "primary", className = "px-4 py-2.5" }: Props) {
  const { pending } = useFormStatus();
  return (
    <button type="submit" disabled={pending || disabled} aria-busy={pending} className={`btn-${variant} relative ${className}`}>
      <span className={`inline-flex items-center gap-2 ${pending ? "invisible" : ""}`}>{children}</span>
      {pending && <LoaderCircle aria-hidden="true" className="absolute size-4 animate-spin motion-reduce:animate-none" />}
    </button>
  );
}
