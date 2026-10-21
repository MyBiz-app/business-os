import { getTranslations } from "next-intl/server";
import type { NextRequest } from "next/server";

import { unwrap } from "@/lib/api";
import { minorDigits, toMajor } from "@/lib/money";
import { isDay, todayIn } from "@/lib/dates";
import { MAX_RANGE_DAYS } from "@/lib/range";
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
  const params = request.nextUrl.searchParams;
  const months = monthRange(params.get("month"), tenant.time_zone);
  // A free range (`from` and `to`) replaces the month, like on the page.
  const from = params.get("from");
  const to = params.get("to");
  const free =
    isDay(from) && isDay(to) && from <= to && to <= todayIn(tenant.time_zone) && (Date.parse(to) - Date.parse(from)) / 86_400_000 < MAX_RANGE_DAYS;
  const { start, end } = free ? { start: from, end: to } : months;
  const month = free ? `${from}_${to}` : months.month;
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
      toMajor(r.amount, r.currency).toFixed(minorDigits(r.currency)),
      r.currency,
      r.simulated ? "1" : "0",
    ]),
  ];
  // Best effort: the export is noted in the audit log, but a failed note never blocks the file.
  await api.POST("/audit-log/exports", { params: scope, body: { kind: "sales_csv", rows: sales.receipts.length } }).catch(() => undefined);
  const csv = "﻿" + rows.map((row) => row.map(cell).join(",")).join("\r\n") + "\r\n";
  return new Response(csv, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="sales-${month}.csv"`,
      "Cache-Control": "no-store",
    },
  });
}
