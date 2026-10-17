import { CrmFrame } from "./crm-frame";

export default function TenantLayout({ children }: LayoutProps<"/">) {
  return <CrmFrame>{children}</CrmFrame>;
}
