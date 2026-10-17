"use client";

import { Lock } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState, useSyncExternalStore } from "react";

import { CHIEF, connect, connectable, disconnect, isCustom, setTeam, teamFrame, treeLayout, type Draft } from "@/lib/ai-structure";

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

type Drag = { key: string; mode: "move" | "link"; x: number; y: number; moved: boolean };

type MapProps = {
  agents: Agent[];
  selected: string | null;
  compact: boolean;
  onPick: (agent: Agent) => void;
  /** The structure being shown: reporting lines, teams and manual places. */
  draft: Draft;
  /** Structure editing: lines are dragged between agents, agents moved, lines clicked away. */
  editing?: boolean;
  onDraft?: (draft: Draft) => void;
};

export function TeamMap({ agents, selected, compact, onPick, draft, editing = false, onDraft }: MapProps) {
  const t = useTranslations("aiTeam");
  const reduced = useReducedMotion();
  const stage = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const tree = editing || isCustom(draft);
  const spots = tree ? treeLayout(agents, draft.parents, draft.pos) : layout(agents, !compact);
  const spotOf = (key: string) => spots.get(key) ?? { x: 50, y: 50 };
  const parentOf = (agent: Agent) => (tree ? (draft.parents[agent.key] ?? CHIEF) : CHIEF);
  const frames = draft.teams
    .map((team) => ({ team, frame: teamFrame(agents.filter((a) => draft.teamOf[a.key] === team.id).map((a) => spotOf(a.key))) }))
    .filter((f) => f.frame !== null);

  function percent(event: React.PointerEvent): { x: number; y: number } {
    const box = stage.current!.getBoundingClientRect();
    return { x: Math.min(100, Math.max(0, ((event.clientX - box.left) / box.width) * 100)), y: Math.min(100, Math.max(0, ((event.clientY - box.top) / box.height) * 100)) };
  }

  function start(event: React.PointerEvent, agent: Agent, mode: Drag["mode"]) {
    if (!editing || !connectable(agent)) return;
    event.stopPropagation();
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    setDrag({ key: agent.key, mode, ...percent(event), moved: false });
  }

  function track(event: React.PointerEvent) {
    if (!drag) return;
    const at = percent(event);
    const moved = drag.moved || Math.hypot(at.x - spotOf(drag.key).x, at.y - spotOf(drag.key).y) > 1.5;
    setDrag({ ...drag, ...at, moved });
  }

  function finish(event: React.PointerEvent) {
    if (!drag || !onDraft) return setDrag(null);
    const at = percent(event);
    if (drag.mode === "link") {
      const hit = document.elementsFromPoint(event.clientX, event.clientY).find((el) => el instanceof HTMLElement && el.dataset.agent && el.dataset.agent !== drag.key);
      const target = hit instanceof HTMLElement ? hit.dataset.agent : undefined;
      if (target) onDraft(connect(draft, agents, drag.key, target));
    } else if (drag.moved) {
      let next: Draft = { ...draft, pos: { ...draft.pos, [drag.key]: at } };
      // Dropped inside a team's frame: the agent joins that team.
      const inside = frames.find(({ frame }) => frame && at.x >= frame.x && at.x <= frame.x + frame.w && at.y >= frame.y && at.y <= frame.y + frame.h);
      if (inside && drag.key !== CHIEF) next = setTeam(next, drag.key, inside.team.id);
      onDraft(next);
    }
    setDrag(null);
  }

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
      ref={stage}
      onPointerMove={track}
      onPointerUp={finish}
      onPointerCancel={() => setDrag(null)}
      className={`ai-stage relative w-full overflow-hidden rounded-3xl border border-border bg-surface transition-[aspect-ratio] duration-700 ${compact ? "aspect-[3/4]" : "aspect-[16/10] min-h-[30rem]"}`}
    >
      {frames.map(({ team, frame }) => (
        <div
          key={team.id}
          aria-hidden="true"
          className="pointer-events-none absolute rounded-3xl border-2 border-dashed"
          style={{ left: `${frame!.x}%`, top: `${frame!.y}%`, width: `${frame!.w}%`, height: `${frame!.h}%`, borderColor: `${team.color}99`, backgroundColor: `${team.color}12` }}
        >
          <span className="absolute -top-3 start-4 rounded-full px-2 text-xs font-semibold" style={{ backgroundColor: team.color, color: "#fff" }} dir="auto">
            {team.name}
          </span>
        </div>
      ))}
      <svg aria-hidden="true" viewBox="0 0 100 100" preserveAspectRatio="none" className={`pointer-events-none absolute inset-0 size-full transition-opacity ${compact ? "opacity-0 duration-150" : "opacity-100 delay-500 duration-500"}`}>
        {agents.map((agent) => {
          const spot = spots.get(agent.key);
          const from = spotOf(parentOf(agent));
          if (!spot || agent.key === CHIEF) return null;
          const live = !INACTIVE.has(agent.state);
          return (
            <g key={agent.key}>
              <line x1={from.x} y1={from.y} x2={spot.x} y2={spot.y} stroke={agent.color} strokeOpacity={live ? 0.4 : 0.14} strokeWidth="1.2" strokeDasharray={live ? undefined : "3 4"} vectorEffect="non-scaling-stroke" />
              {editing && parentOf(agent) !== CHIEF && (
                <line
                  x1={from.x}
                  y1={from.y}
                  x2={spot.x}
                  y2={spot.y}
                  stroke="transparent"
                  strokeWidth="14"
                  vectorEffect="non-scaling-stroke"
                  style={{ pointerEvents: "stroke", cursor: "pointer" }}
                  onClick={() => onDraft?.(disconnect(draft, agent.key))}
                >
                  <title>{t("structure.removeLine", { name: agent.name })}</title>
                </line>
              )}
              {live && !reduced && !compact && !editing && (
                <circle r="0.5" fill={agent.color}>
                  <animateMotion dur={`${3.2 + (agent.key.length % 4) * 0.5}s`} repeatCount="indefinite" path={`M${from.x},${from.y} L${spot.x},${spot.y}`} />
                </circle>
              )}
            </g>
          );
        })}
        {drag?.mode === "link" && <line x1={spotOf(drag.key).x} y1={spotOf(drag.key).y} x2={drag.x} y2={drag.y} stroke="currentColor" strokeWidth="2" strokeDasharray="4 3" vectorEffect="non-scaling-stroke" className="text-primary-ink" />}
      </svg>

      {agents.map((agent, index) => {
        const base = spots.get(agent.key);
        if (!base) return null;
        const spot = drag?.mode === "move" && drag.moved && drag.key === agent.key ? { x: drag.x, y: drag.y } : base;
        const dim = INACTIVE.has(agent.state);
        const isChief = agent.key === "chief";
        const size = compact ? "size-11" : isChief ? "size-24 sm:size-28" : "size-16 sm:size-[4.5rem]";
        const active = selected === agent.key;
        return (
          <button
            key={agent.key}
            type="button"
            data-agent={agent.key}
            onClick={() => {
              if (!editing) onPick(agent);
            }}
            onPointerDown={(event) => start(event, agent, "move")}
            aria-pressed={active}
            aria-label={`${agent.name}, ${agent.role_title}${dim ? `, ${t(`state.${agent.state}`)}` : ""}`}
            title={compact ? `${agent.name} · ${agent.role_title}` : undefined}
            className={`btn-plain group absolute z-10 flex w-32 -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-1 rounded-2xl outline-none ${editing && connectable(agent) ? "cursor-grab touch-none" : ""} ${drag?.key === agent.key && drag.moved ? "!transition-none" : ""} transition-[left,top] duration-700 ease-[cubic-bezier(0.22,1,0.36,1)] focus-visible:ring-2 focus-visible:ring-primary`}
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

      {editing &&
        agents.map((agent) => {
          if (agent.key === CHIEF || !connectable(agent)) return null;
          const spot = drag?.mode === "move" && drag.moved && drag.key === agent.key ? { x: drag.x, y: drag.y } : spotOf(agent.key);
          return (
            <button
              key={`link-${agent.key}`}
              type="button"
              tabIndex={-1}
              onPointerDown={(event) => start(event, agent, "link")}
              aria-label={t("structure.handle", { name: agent.name })}
              title={t("structure.handle", { name: agent.name })}
              className="btn-plain absolute z-20 size-5 -translate-x-1/2 cursor-crosshair touch-none rounded-full border-2 border-primary bg-background shadow hover:bg-primary"
              style={{ left: `${spot.x}%`, top: `calc(${spot.y}% - 3rem)` }}
            />
          );
        })}
    </div>
  );
}
