"use client";

import { Printer } from "lucide-react";

import { logExport } from "@/app/(app)/(tenant)/export-log";

/** `logAs` also notes the print in the audit log (for reports that show business data). */
export function PrintButton({ label, logAs }: { label: string; logAs?: "report_print" }) {
  return (
    <button type="button" onClick={() => {
        if (logAs) void logExport(logAs);
        window.print();
      }} className="btn-secondary px-4 py-2 print:hidden">
      <Printer aria-hidden="true" className="size-4" />
      {label}
    </button>
  );
}
