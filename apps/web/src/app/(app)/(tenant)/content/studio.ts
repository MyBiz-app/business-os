import "server-only";

import { redirect } from "next/navigation";

import { getTenantFor } from "@/lib/tenant";

/** The content studio pages: need `social.read` and the studio module. */
export async function getStudio() {
  const context = await getTenantFor("social.read");
  if (!context.tenant.modules.includes("social_studio")) redirect("/upgrade/social");
  return context;
}
