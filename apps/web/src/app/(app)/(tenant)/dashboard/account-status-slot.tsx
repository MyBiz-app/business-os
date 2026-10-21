import { cookies } from "next/headers";

import { AccountStatusCard } from "@/components/account-status";
import { cardDismissed, STATUS_CARD_COOKIE } from "@/lib/account-status";
import { getAccountStatus } from "@/lib/account-status-server";

/** The account status card on the home page, unless the person closed it for these items. */
export async function AccountStatusSlot() {
  const items = await getAccountStatus();
  if (items.length === 0 || cardDismissed(items, (await cookies()).get(STATUS_CARD_COOKIE)?.value)) return null;
  return <AccountStatusCard items={items} />;
}
