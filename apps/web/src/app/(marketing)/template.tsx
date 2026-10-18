import type { ReactNode } from "react";

import { PageTransition } from "@/components/ui/page-transition";

/** The header and footer stay put; the page between them fades in with a small slide up. */
export default function MarketingTemplate({ children }: { children: ReactNode }) {
  return (
    <PageTransition kind="site">
      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </PageTransition>
  );
}
