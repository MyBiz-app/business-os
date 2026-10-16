"use client";

import { Lock } from "lucide-react";
import { useTranslations } from "next-intl";
import { useSyncExternalStore } from "react";

import { AgentAvatar } from "./agent-avatar";
import type { Agent } from "./types";

const reducedQuery = "(prefers-reduced-motion: reduce)";
function useReducedMotion(): boolean {
  return useSyncExternalStore(
    (notify) => {
      const media = window.matchMedia(reducedQuery);
      media.addEventListener("change", notify);
      return () => media.removeEventListener("change", notify);
    },
    () => window.matchMedia(reducedQuery).matches,
    () => true,
  );
}

type Spot = { x: number; y: number };

/** The chief in the middle, the other built-in agents on a ring around, custom agents on an outer ring. Percent of the stage. */
export function layout(agents: Agent[], wide: boolean): Map<string, Spot> {
  const spots = new Map<string, Spot>();
  const chief = agents.find((a) => a.key === "chief");
  const others = agents.filter((a) => a !== chief);
  const inner = others.filter((a) => a.builtin);
  const outer = others.filter((a) => !a.builtin);
  // A wide stage stretches the rings sideways so the nodes keep an even distance on screen.
  const stretch = wide ? 0.85 : 1.3;
  const ring = (list: Agent[], radius: number, start: number) =>
    list.forEach((agent, i) => {
      const angle = ((start + (360 / Math.max(list.length, 1)) * i) * Math.PI) / 180;
      spots.set(agent.key, { x: 50 + radius * stretch * Math.cos(angle) * (outer.length ? 0.95 : 1), y: 50 + radius * Math.sin(angle) });
    });
  if (chief) spots.set(chief.key, { x: 50, y: 50 });
  ring(inner, outer.length ? 27 : 33, -90);
  ring(outer, 44, -90 + 180 / Math.max(outer.length, 1));
  return spots;
}

const INACTIVE = new Set(["locked", "disabled", "forbidden"]);

export function TeamMap({ agents, selected, compact, onPick }: { agents: Agent[]; selected: string | null; compact: boolean; onPick: (agent: Agent) => void }) {
  const t = useTranslations("aiTeam");
  const reduced = useReducedMotion();
  const spots = layout(agents, !compact);
  const chief = spots.get("chief") ?? { x: 50, y: 50 };

  // Arrow keys walk between the agents in reading order; Enter or Space opens the focused one.
  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const step = ["ArrowRight", "ArrowDown"].includes(event.key) ? 1 : ["ArrowLeft", "ArrowUp"].includes(event.key) ? -1 : 0;
    if (!step) return;
    const nodes = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("button[data-agent]"));
    const at = nodes.indexOf(document.activeElement as HTMLButtonElement);
    if (at < 0) return;
    event.preventDefault();
    nodes[(at + step + nodes.length) % nodes.length]?.focus();
  }

  return (
    <div
      role="group"
      aria-label={t("mapLabel")}
      onKeyDown={onKeyDown}
      className={`ai-stage relative w-full overflow-hidden rounded-3xl border border-border bg-surface transition-[aspect-ratio] duration-700 ${compact ? "aspect-[3/4]" : "aspect-[16/10] min-h-[30rem]"}`}
    >
      <svg aria-hidden="true" viewBox="0 0 100 100" preserveAspectRatio="none" className={`pointer-events-none absolute inset-0 size-full transition-opacity ${compact ? "opacity-0 duration-150" : "opacity-100 delay-500 duration-500"}`}>
        {agents.map((agent) => {
          const spot = spots.get(agent.key);
          if (!spot || agent.key === "chief") return null;
          const live = !INACTIVE.has(agent.state);
          return (
            <g key={agent.key}>
              <line x1={chief.x} y1={chief.y} x2={spot.x} y2={spot.y} stroke={agent.color} strokeOpacity={live ? 0.4 : 0.14} strokeWidth="1.2" strokeDasharray={live ? undefined : "3 4"} vectorEffect="non-scaling-stroke" />
              {live && !reduced && !compact && (
                <circle r="0.5" fill={agent.color}>
                  <animateMotion dur={`${3.2 + (agent.key.length % 4) * 0.5}s`} repeatCount="indefinite" path={`M${chief.x},${chief.y} L${spot.x},${spot.y}`} />
                </circle>
              )}
            </g>
          );
        })}
      </svg>

      {agents.map((agent, index) => {
        const spot = spots.get(agent.key);
        if (!spot) return null;
        const dim = INACTIVE.has(agent.state);
        const isChief = agent.key === "chief";
        const size = compact ? "size-11" : isChief ? "size-24 sm:size-28" : "size-16 sm:size-[4.5rem]";
        const active = selected === agent.key;
        return (
          <button
            key={agent.key}
            type="button"
            data-agent={agent.key}
            onClick={() => onPick(agent)}
            aria-pressed={active}
            aria-label={`${agent.name}, ${agent.role_title}${dim ? `, ${t(`state.${agent.state}`)}` : ""}`}
            title={compact ? `${agent.name} · ${agent.role_title}` : undefined}
            className="group absolute z-10 flex w-32 -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1 rounded-2xl outline-none transition-[left,top] duration-700 ease-[cubic-bezier(0.22,1,0.36,1)] focus-visible:ring-2 focus-visible:ring-primary"
            style={{ left: `${spot.x}%`, top: `${spot.y}%` }}
          >
            <span className={`relative flex ${dim || reduced ? "" : "ai-bob"}`} style={{ animationDelay: `${index * -0.6}s` }}>
              {!dim && <span aria-hidden="true" className={`ai-halo absolute -inset-2 rounded-full blur-md ${active ? "opacity-100" : ""}`} style={{ backgroundColor: agent.color, animationDelay: `${index * -0.4}s` }} />}
              <AgentAvatar
                agent={agent}
                className={`relative shrink-0 ${size} transition-[width,height,filter,transform] duration-700 group-hover:scale-105 ${dim ? "grayscale brightness-[.55]" : ""}`}
              />
              <span aria-hidden="true" className="absolute inset-0 rounded-full transition-shadow" style={{ boxShadow: `0 0 0 ${active ? 4 : 2}px ${dim ? "transparent" : active ? agent.color : `${agent.color}99`}` }} />
              {dim ? (
                <span aria-hidden="true" className="absolute inset-0 grid place-items-center">
                  <Lock className="size-5 text-white drop-shadow" />
                </span>
              ) : (
                <span aria-hidden="true" className="absolute bottom-0 end-0 size-3 rounded-full border-2 border-surface bg-success" />
              )}
            </span>
            <span className={`flex flex-col items-center leading-tight transition-all duration-500 ${compact ? "max-h-0 overflow-hidden opacity-0" : "max-h-16 opacity-100"} ${dim ? "text-muted" : ""}`}>
              <span className="text-sm font-semibold" dir="auto">
                {agent.name}
              </span>
              <span className="text-xs text-muted" dir="auto">
                {agent.role_title}
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}
