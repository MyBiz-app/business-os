import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { Container } from "@/components/layout/container";
import { PageHeader } from "@/components/layout/page-header";
import { unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { canManageSettings, canUseAssistant } from "@/lib/permissions";
import { getBranches, getTenant } from "@/lib/tenant";

import { TeamView } from "./team-view";
import type { Upsell } from "./types";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("aiTeam"))("title") };
}

/** The AI team: every agent of the business on one map, a chat with whichever one is picked. */
export default async function AiTeamPage() {
  const t = await getTranslations("aiTeam");
  const tModules = await getTranslations("modules");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenant();
  if (!canUseAssistant(tenant)) redirect("/dashboard");
  if (!tenant.modules.some((m) => m === "ai_basic" || m === "ai_pro")) redirect("/upgrade/ai");

  const [team, status, catalog, branches] = await Promise.all([
    api.GET("/ai/team", { params: scope }).then(unwrap),
    api.GET("/ai/status", { params: scope }).then(unwrap),
    api.GET("/modules/catalog", { params: { query: { currency: tenant.currency } } }).then(unwrap),
    getBranches(),
  ]);

  const upsells: Record<string, Upsell> = {};
  for (const key of new Set(team.agents.flatMap((a) => (a.upsell_module ? [a.upsell_module] : [])))) {
    const price = catalog.modules.find((m) => m.key === key)?.price;
    upsells[key] = { name: tModules(`names.${key}` as "names.ai_basic"), price: price === undefined ? "" : formatMoney(price, tenant.currency, locale) };
  }

  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <PageHeader title={t("title")} description={t("subtitle")} />
      <TeamView team={team} branches={branches.map(({ id, name }) => ({ id, name }))} enabled={status.enabled} demo={status.demo} upsells={upsells} canAdd={canManageSettings(tenant)} timeZone={tenant.time_zone} />
    </Container>
  );
}
