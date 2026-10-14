import type { ReactNode } from "react";

import { AreaProvider } from "@/providers/area-provider";
import { BusinessProvider } from "@/providers/business-provider";

/** The business first (the client areas), then the areas built on top of it. */
export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <BusinessProvider>
      <AreaProvider>{children}</AreaProvider>
    </BusinessProvider>
  );
}
