import { getTranslations } from "next-intl/server";

import { SideNav } from "@/components/side-nav";
import { getTenant } from "@/lib/tenant";

export default async function TenantLayout({ children }: LayoutProps<"/">) {
  const { tenant } = await getTenant();
  const t = await getTranslations("terms");

  return (
    <div className="flex flex-1 flex-col md:flex-row">
      <SideNav clientsLabel={t(`${tenant.vertical}.clients` as "fitness.clients")} />
      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </div>
  );
}
