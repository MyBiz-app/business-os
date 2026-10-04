import "server-only";

import { redirect } from "next/navigation";

import { getTenantFor } from "@/lib/tenant";

/** The CRM pages: need `clients.read` and the CRM module. */
export async function getCrm() {
  const context = await getTenantFor("clients.read");
  if (!context.tenant.modules.includes("crm")) redirect("/settings/modules");
  return context;
}
