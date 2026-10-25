import { getLocale, getTranslations } from "next-intl/server";
import { businessTerms } from "@/lib/verticals";

import { RouteModal } from "@/components/ui/route-modal";
import { getTenantFor } from "@/lib/tenant";

import { NewSessionBody } from "../../../schedule/new/new-session-body";

export default async function NewSessionModal({ searchParams }: PageProps<"/schedule/new">) {
  const t = await getTranslations();
  const locale = await getLocale();
  const { tenant } = await getTenantFor("schedule.read");
  const { date } = await searchParams;
  return (
    <RouteModal title={businessTerms(t, tenant, locale)("newSession")} size="md">
      <NewSessionBody date={date} />
    </RouteModal>
  );
}
