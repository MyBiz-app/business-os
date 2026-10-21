"use server";

import { getTenant } from "@/lib/tenant";

/** Tells the audit log that data left the business through a CSV or print built in the browser. */
export async function logExport(kind: "sales_csv" | "content_csv" | "report_print", rows = 0): Promise<void> {
  const { api, scope } = await getTenant();
  // Best effort: a failed note must never stop the person from getting their file.
  await api.POST("/audit-log/exports", { params: scope, body: { kind, rows } }).catch(() => undefined);
}
