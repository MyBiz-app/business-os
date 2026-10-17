"use client";

import { Plus, RotateCcw, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";

import { CHIEF, connect, connectable, removeTeam, setTeam, type Draft } from "@/lib/ai-structure";

import type { Agent } from "./types";

const TEAM_COLORS = ["#2563EB", "#7C3AED", "#06B6D4", "#10B981", "#F59E0B", "#F43F5E"];

type Props = {
  agents: Agent[];
  draft: Draft;
  saving: boolean;
  error: string | null;
  onChange: (draft: Draft) => void;
  onRelayout: () => void;
  onSave: () => void;
  onCancel: () => void;
};

/** Structure editing without a mouse: who each agent reports to and which team it is in, plus the teams themselves. Also the way to edit on a phone. */
export function StructurePanel({ agents, draft, saving, error, onChange, onRelayout, onSave, onCancel }: Props) {
  const t = useTranslations("aiTeam.structure");
  const field = "rounded-xl border border-border bg-background px-2 py-1.5 text-sm";

  function addTeam() {
    const index = draft.teams.length;
    onChange({ ...draft, teams: [...draft.teams, { id: crypto.randomUUID(), name: t("newTeamName", { n: index + 1 }), color: TEAM_COLORS[index % TEAM_COLORS.length]!, lead_key: null }] });
  }

  function patchTeam(id: string, patch: Partial<Draft["teams"][number]>) {
    onChange({ ...draft, teams: draft.teams.map((team) => (team.id === id ? { ...team, ...patch } : team)) });
  }

  return (
    <section aria-labelledby="structure-title" className="card flex flex-col gap-4 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 id="structure-title" className="font-semibold">
            {t("title")}
          </h2>
          <p className="text-sm text-muted">{t("hint")}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={onRelayout} className="btn-secondary inline-flex items-center gap-1.5 px-3 py-1.5 text-sm">
            <RotateCcw aria-hidden="true" className="size-4" />
            {t("relayout")}
          </button>
          <button type="button" onClick={onCancel} disabled={saving} className="btn-secondary px-3 py-1.5 text-sm">
            {t("cancel")}
          </button>
          <button type="button" onClick={onSave} disabled={saving} className="btn-primary px-3 py-1.5 text-sm">
            {saving ? t("saving") : t("save")}
          </button>
        </div>
      </div>
      {error && (
        <p role="alert" className="rounded-xl border border-danger/50 bg-danger/10 p-3 text-sm">
          {t(`errors.${error === "locked_agent" || error === "cycle" ? error : "generic"}`)}
        </p>
      )}

      <ul className="grid gap-2" aria-label={t("agentsLabel")}>
        {agents.map((agent) => {
          const locked = !connectable(agent);
          return (
            <li key={agent.key} className="grid items-center gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)]">
              <span className={`truncate text-sm font-medium ${locked ? "text-muted" : ""}`} dir="auto">
                <span aria-hidden="true" className="me-2 inline-block size-2.5 rounded-full" style={{ backgroundColor: agent.color }} />
                {agent.name}
                <span className="ms-2 text-xs text-muted">{agent.role_title}</span>
              </span>
              {agent.key === CHIEF ? (
                <span className="text-sm text-muted">{t("top")}</span>
              ) : (
                <label className="flex items-center gap-2 text-sm">
                  <span className="shrink-0 text-muted">{t("reportsTo")}</span>
                  <select
                    className={`${field} min-w-0 flex-1`}
                    disabled={locked}
                    value={draft.parents[agent.key] ?? CHIEF}
                    onChange={(event) => onChange(connect(draft, agents, agent.key, event.target.value))}
                    aria-label={t("reportsToFor", { name: agent.name })}
                  >
                    {agents
                      .filter((other) => other.key !== agent.key && connectable(other))
                      .map((other) => (
                        <option key={other.key} value={other.key}>
                          {other.name}
                        </option>
                      ))}
                  </select>
                </label>
              )}
              <label className="flex items-center gap-2 text-sm">
                <span className="shrink-0 text-muted">{t("team")}</span>
                <select
                  className={`${field} min-w-0 flex-1`}
                  disabled={locked || agent.key === CHIEF}
                  value={draft.teamOf[agent.key] ?? ""}
                  onChange={(event) => onChange(setTeam(draft, agent.key, event.target.value || null))}
                  aria-label={t("teamFor", { name: agent.name })}
                >
                  <option value="">{t("noTeam")}</option>
                  {draft.teams.map((team) => (
                    <option key={team.id} value={team.id}>
                      {team.name}
                    </option>
                  ))}
                </select>
              </label>
            </li>
          );
        })}
      </ul>

      <div className="flex flex-col gap-2 border-t border-border pt-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">{t("teams")}</h3>
          <button type="button" onClick={addTeam} disabled={draft.teams.length >= 20} className="btn-secondary inline-flex items-center gap-1.5 px-3 py-1.5 text-sm">
            <Plus aria-hidden="true" className="size-4" />
            {t("addTeam")}
          </button>
        </div>
        {draft.teams.length === 0 && <p className="text-sm text-muted">{t("noTeams")}</p>}
        {draft.teams.map((team) => (
          <div key={team.id} className="flex flex-wrap items-center gap-2">
            <input type="color" value={team.color} onChange={(event) => patchTeam(team.id, { color: event.target.value.toUpperCase() })} aria-label={t("teamColor")} className="size-8 shrink-0 rounded-lg border border-border bg-background p-0.5" />
            <input value={team.name} maxLength={60} dir="auto" onChange={(event) => patchTeam(team.id, { name: event.target.value })} aria-label={t("teamName")} className={`${field} min-w-0 flex-1`} />
            <label className="flex items-center gap-2 text-sm">
              <span className="text-muted">{t("lead")}</span>
              <select className={field} value={team.lead_key ?? ""} onChange={(event) => patchTeam(team.id, { lead_key: event.target.value || null })} aria-label={t("leadFor", { name: team.name })}>
                <option value="">{t("noLead")}</option>
                {agents
                  .filter((a) => draft.teamOf[a.key] === team.id)
                  .map((a) => (
                    <option key={a.key} value={a.key}>
                      {a.name}
                    </option>
                  ))}
              </select>
            </label>
            <button type="button" onClick={() => onChange(removeTeam(draft, team.id))} aria-label={t("removeTeam", { name: team.name })} className="btn-plain rounded-lg p-2 text-muted hover:text-danger">
              <Trash2 aria-hidden="true" className="size-4" />
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}
