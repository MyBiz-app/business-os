import { getTranslations } from "next-intl/server";
import { termsOf } from "@business-os/verticals";

import { RouteModal } from "@/components/ui/route-modal";
import { getTenantFor } from "@/lib/tenant";

import { NewSessionBody } from "../../../schedule/new/new-session-body";

export default async function NewSessionModal({ searchParams }: PageProps<"/schedule/new">) {
  const t = await getTranslations();
  const { tenant } = await getTenantFor("schedule.read");
  const { date } = await searchParams;
  return (
    <RouteModal title={t(`terms.${termsOf(tenant.vertical)}.newSession` as "terms.fitness.newSession")} size="md">
      <NewSessionBody date={date} />
    </RouteModal>
  );
}
