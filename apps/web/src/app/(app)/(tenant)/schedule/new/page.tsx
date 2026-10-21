import { getTranslations } from "next-intl/server";
import { termsOf } from "@business-os/verticals";

import { BackLink } from "@/components/back-link";
import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { getTenantFor } from "@/lib/tenant";

import { NewSessionBody } from "./new-session-body";

export default async function NewSessionPage({ searchParams }: PageProps<"/schedule/new">) {
  const t = await getTranslations();
  const { tenant } = await getTenantFor("schedule.read");
  const { date } = await searchParams;
  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <BackLink href="/schedule" label={t("schedule.back")} />
      <PageHeader title={t(`terms.${termsOf(tenant.vertical)}.newSession` as "terms.fitness.newSession")} />
      <NewSessionBody date={date} />
    </Container>
  );
}
