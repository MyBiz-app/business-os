import type { ReactNode } from "react";

import { CrmFrame } from "./crm-frame";

export default function TenantLayout({ children, modal }: LayoutProps<"/"> & { modal?: ReactNode }) {
  return <CrmFrame modal={modal}>{children}</CrmFrame>;
}
