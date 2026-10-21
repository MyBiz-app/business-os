"use client";

import { Lock } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import type { ChatRole } from "./actions";
import { Button } from "@/components/ui/button";

export type AgentCard = {
  key: ChatRole;
  color: string;
  chief: boolean;
  ready: boolean;
  enabled: boolean;
  name_he: string | null;
  name_en: string | null;
  portrait_url: string | null;
  x: number | null;
  y: number | null;
  instructions: string | null;
};

type Spot = { x: number; y: number };

/** The chief in the middle, the other agents on a ring around it; a place the team set wins. Percent of the stage. */
export function spots(agents: AgentCard[]): Map<string, Spot> {
  const places = new Map<string, Spot>();
  const others = agents.filter((agent) => !agent.chief);
  others.forEach((agent, index) => {
    const angle = ((-90 + (360 / Math.max(others.length, 1)) * index) * Math.PI) / 180;
    places.set(agent.key, { x: 50 + 38 * Math.cos(angle), y: 50 + 36 * Math.sin(angle) });
  });
  for (const agent of agents) {
    if (agent.chief) places.set(agent.key, { x: 50, y: 50 });
    if (agent.x !== null && agent.y !== null) places.set(agent.key, { x: agent.x, y: agent.y });
  }
  return places;
}

/** The name the team gave the agent in this language, or the built-in one. */
export function useAgentName(): (agent: AgentCard) => string {
  const t = useTranslations("platform.ai");
  const locale = useLocale();
  return (agent) => (locale === "he" ? agent.name_he : agent.name_en) ?? t(`agents.${agent.key}.name`);
}

function Face({ agent, name, className }: { agent: AgentCard; name: string; className: string }) {
  if (agent.portrait_url) {
    // eslint-disable-next-line @next/next/no-img-element -- a portrait the team supplied, any https address
    return <img src={agent.portrait_url} alt="" draggable={false} className={`rounded-full object-cover ${className}`} />;
  }
  return (
    <span aria-hidden="true" className={`grid place-items-center rounded-full font-semibold text-white ${className}`} style={{ backgroundColor: agent.color }}>
      {Array.from(name)[0] ?? "?"}
    </span>
  );
}

/** MyBiz's own AI team as a map (the chief in the middle), the same idea as a business's AI team. Picking an agent selects it; agents still to come and agents switched off are shown dim. */
export function AgentsMap({ agents, selected, onPick }: { agents: AgentCard[]; selected: ChatRole; onPick: (agent: AgentCard) => void }) {
  const t = useTranslations("platform.ai");
  const nameOf = useAgentName();
  const places = spots(agents);
  const stateOf = (agent: AgentCard) => (!agent.ready ? "soon" : !agent.enabled ? "off" : "on");

  const label = (agent: AgentCard) => {
    const state = stateOf(agent);
    return `${nameOf(agent)}, ${t(`agents.${agent.key}.title`)}${state === "on" ? "" : `, ${t(`agentState.${state}`)}`}`;
  };

  return (
    <div>
      <div role="group" aria-label={t("mapLabel")} className="relative hidden aspect-[16/10] min-h-[28rem] w-full overflow-hidden rounded-3xl border border-border bg-surface sm:block">
        <svg aria-hidden="true" viewBox="0 0 100 100" preserveAspectRatio="none" className="pointer-events-none absolute inset-0 size-full">
          {agents.map((agent) => {
            const place = places.get(agent.key);
            const middle = places.get(agents.find((a) => a.chief)?.key ?? "") ?? { x: 50, y: 50 };
            if (!place || agent.chief) return null;
            return <line key={agent.key} x1={middle.x} y1={middle.y} x2={place.x} y2={place.y} stroke={agent.color} strokeOpacity={stateOf(agent) === "on" ? 0.4 : 0.14} strokeWidth="1.2" strokeDasharray={stateOf(agent) === "on" ? undefined : "3 4"} vectorEffect="non-scaling-stroke" />;
          })}
        </svg>
        {agents.map((agent) => {
          const place = places.get(agent.key);
          if (!place) return null;
          const dim = stateOf(agent) !== "on";
          const active = selected === agent.key;
          return (
            <Button variant="plain"
              key={agent.key}
              aria-pressed={active}
              aria-label={label(agent)}
              onClick={() => onPick(agent)}
              style={{ left: `${place.x}%`, top: `${place.y}%` }}
              className="group absolute z-10 flex w-32 -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1 rounded-2xl outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <span className="relative flex">
                <Face agent={agent} name={nameOf(agent)} className={`${agent.chief ? "size-24" : "size-16"} transition-transform group-hover:scale-105 ${dim ? "grayscale brightness-[.55]" : ""}`} />
                <span aria-hidden="true" className="absolute inset-0 rounded-full" style={{ boxShadow: `0 0 0 ${active ? 4 : 2}px ${dim ? "transparent" : active ? agent.color : `${agent.color}99`}` }} />
                {dim && (
                  <span aria-hidden="true" className="absolute inset-0 grid place-items-center">
                    <Lock className="size-5 text-white drop-shadow" />
                  </span>
                )}
              </span>
              <span className={`flex flex-col items-center leading-tight ${dim ? "text-muted" : ""}`}>
                <span className="text-sm font-semibold" dir="auto">{nameOf(agent)}</span>
                <span className="text-xs text-muted" dir="auto">{t(`agents.${agent.key}.title`)}</span>
              </span>
            </Button>
          );
        })}
      </div>

      <ul className="grid grid-cols-2 gap-3 sm:hidden">
        {agents.map((agent) => {
          const dim = stateOf(agent) !== "on";
          return (
            <li key={agent.key}>
              <Button
                variant="plain"
                aria-pressed={selected === agent.key}
                aria-label={label(agent)}
                onClick={() => onPick(agent)}
                className={`flex w-full items-center gap-3 rounded-2xl border p-3 text-start ${selected === agent.key ? "border-primary" : "border-border"}`}
              >
                <Face agent={agent} name={nameOf(agent)} className={`size-11 shrink-0 ${dim ? "grayscale brightness-[.55]" : ""}`} />
                <span className={`flex min-w-0 flex-col leading-tight ${dim ? "text-muted" : ""}`}>
                  <span className="truncate text-sm font-semibold" dir="auto">{nameOf(agent)}</span>
                  <span className="truncate text-xs text-muted" dir="auto">{t(`agents.${agent.key}.title`)}</span>
                </span>
              </Button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
