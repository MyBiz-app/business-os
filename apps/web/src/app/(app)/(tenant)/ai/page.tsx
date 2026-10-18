import type { Metadata } from "next";
import { getLocale, getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";

import { Container } from "@/components/layout/container";
import { unwrap } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import { canManageSettings, canUseAssistant } from "@/lib/permissions";
import { getBranches, getTenant } from "@/lib/tenant";

import { ProactiveSettingsPanel } from "./proactive-settings";
import { TasksBoard } from "./tasks-board";
import { TeamView } from "./team-view";
import type { MeterDetails } from "./usage-meter";
import type { Upsell } from "./types";

export async function generateMetadata(): Promise<Metadata> {
  return { title: (await getTranslations("aiTeam"))("title") };
}

/** The AI team: every agent of the business on one map, a chat with whichever one is picked. */
export default async function AiTeamPage({ searchParams }: PageProps<"/ai">) {
  const { agent } = await searchParams;
  const tModules = await getTranslations("modules");
  const locale = await getLocale();
  const { tenant, api, scope } = await getTenant();
  if (!canUseAssistant(tenant)) redirect("/dashboard");
  if (!tenant.modules.some((m) => m === "ai_basic" || m === "ai_pro")) redirect("/upgrade/ai");

  const [team, status, catalog, branches, roles, tasks, proactive, meter, tours] = await Promise.all([
    api.GET("/ai/team", { params: scope }).then(unwrap),
    api.GET("/ai/status", { params: scope }).then(unwrap),
    api.GET("/modules/catalog", { params: { query: { currency: tenant.currency } } }).then(unwrap),
    getBranches(),
    // Choosing who may use an agent lists the business's own roles; without access to them the built-in ones remain.
    api.GET("/roles", { params: scope }).then((r) => r.data?.custom.map(({ id, name }) => ({ id, name })) ?? []),
    api.GET("/ai/tasks", { params: scope }).then(unwrap),
    api.GET("/ai/tasks/proactive", { params: scope }).then(unwrap),
    api.GET("/ai/meter", { params: scope }).then(unwrap),
    // The first-time guide is a nicety: if this fails the page still opens, without it.
    api.GET("/me/tours").then((r) => r.data?.seen ?? ["ai_team"]),
  ]);

  // The usage window is for those who manage the team: the whole business, by person and agent.
  let meterDetails: MeterDetails | null = null;
  if (team.can_manage) {
    const [usage, breakdown, staff] = await Promise.all([
      api.GET("/ai/usage", { params: scope }).then(unwrap),
      api.GET("/ai/usage/breakdown", { params: scope }).then(unwrap),
      api.GET("/staff", { params: scope }).then((r) => r.data?.members ?? []),
    ]);
    meterDetails = {
      usage,
      breakdown,
      people: Object.fromEntries(staff.map((m) => [m.user_id, m.full_name ?? m.email])),
      agents: Object.fromEntries(team.agents.map((a) => [a.key, a.name])),
    };
  }

  const upsells: Record<string, Upsell> = {};
  for (const key of new Set(team.agents.flatMap((a) => (a.upsell_module ? [a.upsell_module] : [])))) {
    const price = catalog.modules.find((m) => m.key === key)?.price;
    upsells[key] = { name: tModules(`names.${key}` as "names.ai_basic"), price: price === undefined ? "" : formatMoney(price, tenant.currency, locale) };
  }

  return (
    <Container as="main" size="full" className="enter flex flex-1 flex-col gap-6 py-8 sm:py-10">
      <TeamView team={team} branches={branches.map(({ id, name }) => ({ id, name }))} enabled={status.enabled} demo={status.demo} upsells={upsells} canAdd={canManageSettings(tenant)} timeZone={tenant.time_zone} roles={roles} tourSeen={tours.includes("ai_team")} initialAgent={typeof agent === "string" ? agent : null} meter={meter} meterDetails={meterDetails} />
      {/* The two cards share one width, padding and header, side by side on a wide screen. */}
      <div className="grid gap-6 xl:grid-cols-2 xl:items-start">
        <ProactiveSettingsPanel settings={proactive} timeZone={tenant.time_zone} />
        <TasksBoard board={tasks} agents={Object.fromEntries(team.agents.map((a) => [a.key, a.name]))} timeZone={tenant.time_zone} />
      </div>
    </Container>
  );
}
