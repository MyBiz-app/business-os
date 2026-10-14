import type { ReactNode } from "react";

import { AreaProvider } from "@/providers/area-provider";
import { PlatformProvider } from "@/providers/platform-provider";
import { StaffProvider } from "@/providers/staff-provider";
import { BusinessProvider } from "@/providers/business-provider";

/** The client businesses first, then the areas built on them, then the business being worked in. */
export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <BusinessProvider>
      <AreaProvider>
        <StaffProvider>
          <PlatformProvider>{children}</PlatformProvider>
        </StaffProvider>
      </AreaProvider>
    </BusinessProvider>
  );
}
