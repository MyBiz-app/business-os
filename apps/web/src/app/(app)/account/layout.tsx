import type { ReactNode } from "react";

import { getTenant } from "@/lib/tenant";

import { CrmFrame } from "../(tenant)/crm-frame";

/** Whether the person has a business to show the CRM frame for. A closed or suspended business,
 * a missing second step or no business at all leaves the page in the plain app shell, so this page
 * (where two-step sign-in is turned on) always opens. */
async function hasBusiness(): Promise<boolean> {
  try {
    await getTenant();
    return true;
  } catch {
    return false;
  }
}

/** The profile sits inside the CRM frame (like settings) whenever the person has a business. */
export default async function AccountLayout({ children }: { children: ReactNode }) {
  return (await hasBusiness()) ? <CrmFrame>{children}</CrmFrame> : children;
}
