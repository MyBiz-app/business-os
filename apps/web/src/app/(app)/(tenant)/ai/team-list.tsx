"use client";

import { Lock } from "lucide-react";
import { useTranslations } from "next-intl";

import { AgentAvatar } from "./agent-avatar";
import type { Agent } from "./types";
import { Button } from "@/components/ui/button";

/** The same team as the map, as plain cards: for phones, screen readers and anyone who prefers a list. */
export function TeamList({ agents, selected, compact = false, onPick }: { agents: Agent[]; selected: string | null; compact?: boolean; onPick: (agent: Agent) => void }) {
  const t = useTranslations("aiTeam");
  return (
    <ul className={compact ? "grid gap-2" : "grid gap-3 sm:grid-cols-2 xl:grid-cols-3"} aria-label={t("listLabel")}>
      {agents.map((agent) => {
        const dim = agent.state !== "active";
        return (
          <li key={agent.key}>
            <Button variant="plain"
              type="button"
              onClick={() => onPick(agent)}
              aria-pressed={selected === agent.key}
              className="card flex w-full items-center gap-3 p-3 text-start transition hover:-translate-y-0.5"
              style={{ boxShadow: selected === agent.key ? `0 0 0 2px ${agent.color}` : undefined }}
            >
              <span className="relative flex shrink-0">
                <AgentAvatar agent={agent} className={`size-14 ${dim ? "grayscale brightness-[.55]" : ""}`} />
                {dim && (
                  <span aria-hidden="true" className="absolute inset-0 grid place-items-center">
                    <Lock className="size-5 text-white drop-shadow" />
                  </span>
                )}
              </span>
              <span className="flex min-w-0 flex-col">
                <span className={`truncate font-semibold ${dim ? "text-muted" : ""}`} dir="auto">
                  {agent.name}
                </span>
                <span className="truncate text-sm text-muted" dir="auto">
                  {agent.role_title}
                </span>
                <span className={`text-xs ${agent.state === "active" ? "text-success-ink" : "text-muted"}`}>{t(`state.${agent.state}`)}</span>
              </span>
            </Button>
          </li>
        );
      })}
    </ul>
  );
}
