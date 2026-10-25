import { useMemo } from "react";

import { useSession } from "@business-os/app-kit/providers/session-provider";
import type { DataContext } from "@/lib/client-data";
import { useBusiness } from "@/providers/business-provider";

/** Who is asking and for which business, for the shared loaders (null until a business is open). */
export function useDataContext(): DataContext | null {
  const { api, scope, business } = useBusiness();
  const { session } = useSession();
  const userId = session?.user.id;
  return useMemo(() => (business && userId ? { api, scope, business, userId } : null), [api, scope, business, userId]);
}
