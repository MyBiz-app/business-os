"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { unwrap } from "@/lib/api";
import { getTenant } from "@/lib/tenant";
import { isUpgrade, UPGRADES } from "@/lib/upgrades";

/** "Add to my plan" on a locked module's preview: the module joins the plan (and the next
 * invoice) and its page opens. */
export async function addToPlan(offer: string, key: string): Promise<void> {
  if (!isUpgrade(offer) || !(UPGRADES[offer].modules as readonly string[]).includes(key)) return;
  const { api, scope } = await getTenant();
  unwrap(
    await api.POST("/tenants/current/modules/{key}", {
      params: { ...scope, path: { key: key as "crm" } },
    }),
  );
  revalidatePath("/", "layout");
  redirect(UPGRADES[offer].href);
}
