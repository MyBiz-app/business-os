import type { ReactNode } from "react";

import { PageTransition } from "@/components/ui/page-transition";

/** Between sign-in screens the shell stays; the form swaps with the landing page's fade and slide. */
export default function AuthTemplate({ children }: { children: ReactNode }) {
  return <PageTransition kind="site">{children}</PageTransition>;
}
