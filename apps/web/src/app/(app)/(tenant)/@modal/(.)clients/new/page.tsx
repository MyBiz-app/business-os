import { getTranslations } from "next-intl/server";
import { termsOf } from "@business-os/verticals";

import { RouteModal } from "@/components/ui/route-modal";
import { getTenantFor } from "@/lib/tenant";

import { NewClientBody } from "../../../clients/new/new-client-body";

export default async function NewClientModal() {
  const t = await getTranslations();
  const { tenant } = await getTenantFor("clients.read");
  return (
    <RouteModal title={t(`terms.${termsOf(tenant.vertical)}.newClient` as "terms.fitness.newClient")} size="md">
      <NewClientBody />
    </RouteModal>
  );
}
