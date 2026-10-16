"use client";

import { Download } from "lucide-react";

/** Saves the rows as a CSV file (built in the browser from what the page already shows). */
export function CsvButton({ label, filename, rows }: { label: string; filename: string; rows: (string | number)[][] }) {
  const download = () => {
    const quote = (cell: string | number) => `"${String(cell).replaceAll('"', '""')}"`;
    const text = `﻿${rows.map((row) => row.map(quote).join(",")).join("\r\n")}`;
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
  };
  return (
    <button type="button" onClick={download} className="btn-secondary px-4 py-2 print:hidden">
      <Download aria-hidden="true" className="size-4" />
      {label}
    </button>
  );
}
