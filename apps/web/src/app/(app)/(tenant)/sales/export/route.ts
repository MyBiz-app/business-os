import { getTranslations } from "next-intl/server";
import type { NextRequest } from "next/server";

import { unwrap } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

import { monthRange } from "../month";

const cell = (value: string | number) => {
  const text = String(value);
  // Quote everything; neutralize spreadsheet formulas in user-entered text.
  const safe = /^[=+\-@]/.test(text) ? `'${text}` : text;
  return `"${safe.replaceAll('"', '""')}"`;
};

/** The month's receipts as CSV (UTF-8 with BOM, so Excel shows Hebrew correctly). */
export async function GET(request: NextRequest) {
  const { tenant, api, scope } = await getTenantFor("reports.read");
  const t = await getTranslations("sales");
  const tReceipts = await getTranslations("receipts");
  const { month, start, end } = monthRange(request.nextUrl.searchParams.get("month"), tenant.time_zone);
  const sales = unwrap(await api.GET("/sales", { params: { ...scope, query: { start, end } } }));
  const dateOf = (instant: string) =>
    new Intl.DateTimeFormat("en-CA", { timeZone: tenant.time_zone, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(instant));
  const rows = [
    t.raw("csvHeader") as string[],
    ...sales.receipts.map((r) => [
      r.number,
      dateOf(r.issued_at),
      r.client_name,
      r.client_email ?? "",
      r.description,
      tReceipts(`methods.${r.method}`),
      (r.amount / 100).toFixed(2),
      r.currency,
      r.simulated ? "1" : "0",
    ]),
  ];
  const csv = "﻿" + rows.map((row) => row.map(cell).join(",")).join("\r\n") + "\r\n";
  return new Response(csv, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="sales-${month}.csv"`,
      "Cache-Control": "no-store",
    },
  });
}
