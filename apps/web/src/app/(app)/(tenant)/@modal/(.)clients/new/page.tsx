import { getLocale, getTranslations } from "next-intl/server";
import { businessTerms } from "@/lib/verticals";

import { RouteModal } from "@/components/ui/route-modal";
import { getTenantFor } from "@/lib/tenant";

import { NewClientBody } from "../../../clients/new/new-client-body";

export default async function NewClientModal() {
  const t = await getTranslations();
  const locale = await getLocale();
  const { tenant } = await getTenantFor("clients.read");
  return (
    <RouteModal title={businessTerms(t, tenant, locale)("newClient")} size="md">
      <NewClientBody />
    </RouteModal>
  );
}
