import { getTranslations } from "next-intl/server";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { unwrap } from "@/lib/api";
import { getTenantFor } from "@/lib/tenant";

import { MigrationHub } from "./migration-hub";

/** "Move to MyBiz" (round 6, M1): bring an existing business over from its previous system. */
export default async function MigrationPage() {
  const t = await getTranslations("migration");
  const { tenant, api, scope } = await getTenantFor("migration.manage");
  const sessions = unwrap(await api.GET("/migration/sessions", { params: scope }));
  const draft = sessions.find((s) => s.status === "draft") ?? null;
  // The latest move that was imported and still stands: its clients can still be told.
  const moved = sessions.find((s) => s.status === "imported" && s.batches.some((b) => b.status === "done")) ?? null;
  const batches = sessions.flatMap((s) => s.batches).filter((b) => b.status === "done");

  return (
    <Container as="main" size="narrow" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader title={t("title")} description={t("intro")} />
      <MigrationHub draft={draft} movedId={moved?.id ?? null} batches={batches} timeZone={tenant.time_zone} />
    </Container>
  );
}
