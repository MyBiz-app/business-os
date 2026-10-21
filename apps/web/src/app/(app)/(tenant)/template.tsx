import type { ReactNode } from "react";

import { PageTransition } from "@/components/ui/page-transition";

/** The side menu and the header stay put; only the content area swaps, with a quick fade. */
export default function TenantTemplate({ children }: { children: ReactNode }) {
  return (
    <PageTransition kind="app">
      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </PageTransition>
  );
}
