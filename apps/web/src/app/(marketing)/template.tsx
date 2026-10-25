import type { ReactNode } from "react";

import { MarketingFooter } from "@/components/marketing/marketing-footer";
import { PageTransition } from "@/components/ui/page-transition";

/** The header stays put; the page and the footer fade together as one piece, so a footer link does
 * not show the old footer for a moment next to the new page. */
export default function MarketingTemplate({ children }: { children: ReactNode }) {
  return (
    <PageTransition kind="site">
      <div className="site-page flex min-w-0 flex-1 flex-col">
        <div className="flex flex-1 flex-col">{children}</div>
        <MarketingFooter />
      </div>
    </PageTransition>
  );
}
