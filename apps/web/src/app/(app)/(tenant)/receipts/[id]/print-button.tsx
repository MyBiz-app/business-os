"use client";

import { Printer } from "lucide-react";

export function PrintButton({ label }: { label: string }) {
  return (
    <button type="button" onClick={() => window.print()} className="btn-secondary px-4 py-2 print:hidden">
      <Printer aria-hidden="true" className="size-4" />
      {label}
    </button>
  );
}
