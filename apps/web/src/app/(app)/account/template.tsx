import type { ReactNode } from "react";

import { PageTransition } from "@/components/ui/page-transition";

/** The profile and its sections swap with a quick fade (the CRM frame, when present, stays put). */
export default function AccountTemplate({ children }: { children: ReactNode }) {
  return (
    <PageTransition kind="app">
      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </PageTransition>
  );
}
