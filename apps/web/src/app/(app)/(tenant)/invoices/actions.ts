"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { ApiError, unwrap } from "@/lib/api";
import type { FormState } from "@/lib/form-state";
import { readIssueBody } from "@/lib/issued-documents";
import { getTenantFor } from "@/lib/tenant";

/** The refusals the API gives that the form explains in words. */
const REASONS = ["exempt_dealer_no_tax_invoice", "legal_details_missing", "credit_exceeds_invoice", "unknown_invoice", "unknown_client"] as const;
export type IssueState = FormState & { reason?: (typeof REASONS)[number] };

/** Issues a document: takes the next number of its kind and stores the PDF. It is never edited
 * afterwards; a mistake is fixed with a credit note. */
export async function issueDocument(_state: IssueState, formData: FormData): Promise<IssueState> {
  const { api, scope, tenant } = await getTenantFor("sales.manage");
  const body = readIssueBody(formData, tenant.currency);
  if (!body) return { error: "invalid" };
  let id: string;
  try {
    id = unwrap(await api.POST("/issued-documents", { params: scope, body })).id;
  } catch (error) {
    if (error instanceof ApiError) {
      const detail = (error.body as { detail?: unknown } | null)?.detail;
      const reason = REASONS.find((r) => r === detail);
      if (reason) return { error: "invalid", reason };
      if (error.status === 422) return { error: "invalid" };
    }
    return { error: "generic" };
  }
  revalidatePath("/invoices");
  redirect(`/invoices/${id}`);
}
