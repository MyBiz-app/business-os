"use client";

/** Opens the browser print dialog (legal documents). */
export function PrintButton({ label }: { label: string }) {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      className="w-fit rounded-xl border border-border px-4 py-2 text-sm font-semibold transition-colors hover:bg-foreground/5 print:hidden"
    >
      {label}
    </button>
  );
}
