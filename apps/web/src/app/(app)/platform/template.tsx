import type { ReactNode } from "react";

import { PageTransition } from "@/components/ui/page-transition";

/** The console's side menu stays put; only the page content swaps, with a quick fade. */
export default function PlatformTemplate({ children }: { children: ReactNode }) {
  return (
    <PageTransition kind="app">
      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </PageTransition>
  );
}
