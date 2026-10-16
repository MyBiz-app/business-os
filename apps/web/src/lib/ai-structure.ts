/** The AI team's structure as the map edits it: who reports to whom, teams and manual positions. Pure functions, no React. */

export const CHIEF = "chief";

export type StructureAgent = {
  key: string;
  state: string;
  reports_to?: string | null;
  team_id?: string | null;
  map_x?: number | null;
  map_y?: number | null;
};

export type StructureTeam = { id: string; name: string; color: string; lead_key?: string | null };

export type Draft = {
  parents: Record<string, string | null>;
  teamOf: Record<string, string | null>;
  teams: StructureTeam[];
  /** Manual positions in percent of the stage; an agent without one is placed by the tree. */
  pos: Record<string, { x: number; y: number }>;
};

export type Spot = { x: number; y: number };

export function draftOf(agents: StructureAgent[], teams: StructureTeam[]): Draft {
  const draft: Draft = { parents: {}, teamOf: {}, teams: teams.map((t) => ({ ...t })), pos: {} };
  for (const a of agents) {
    draft.parents[a.key] = a.key === CHIEF ? null : (a.reports_to ?? CHIEF);
    draft.teamOf[a.key] = a.team_id ?? null;
    if (a.map_x != null && a.map_y != null) draft.pos[a.key] = { x: a.map_x, y: a.map_y };
  }
  return draft;
}

/** True when anything deviates from the default shape (everyone under the chief, no teams, no manual place). */
export function isCustom(draft: Draft): boolean {
  return (
    draft.teams.length > 0 ||
    Object.keys(draft.pos).length > 0 ||
    Object.entries(draft.parents).some(([key, parent]) => key !== CHIEF && parent !== CHIEF)
  );
}

/** Would `child` reporting to `parent` close a loop (or report to itself)? */
export function wouldCycle(parents: Record<string, string | null>, child: string, parent: string): boolean {
  if (child === parent) return true;
  let at: string | null | undefined = parent;
  const seen = new Set<string>();
  while (at && at !== CHIEF && !seen.has(at)) {
    if (at === child) return true;
    seen.add(at);
    at = parents[at] ?? CHIEF;
  }
  return false;
}

/** Locked agents are shown but cannot be wired into the structure. */
export function connectable(agent: StructureAgent): boolean {
  return agent.state !== "locked";
}

/** Sets who `child` reports to; returns the same draft when the change is not allowed. */
export function connect(draft: Draft, agents: StructureAgent[], child: string, parent: string): Draft {
  const a = agents.find((x) => x.key === child);
  const b = agents.find((x) => x.key === parent);
  if (!a || !b || child === CHIEF || !connectable(a) || !connectable(b)) return draft;
  if (wouldCycle(draft.parents, child, parent)) return draft;
  return { ...draft, parents: { ...draft.parents, [child]: parent } };
}

/** Removing a line sends the agent back under the chief. */
export function disconnect(draft: Draft, child: string): Draft {
  if (child === CHIEF) return draft;
  return { ...draft, parents: { ...draft.parents, [child]: CHIEF } };
}

export function setTeam(draft: Draft, key: string, teamId: string | null): Draft {
  const teams = draft.teams.map((t) => (t.lead_key === key && t.id !== teamId ? { ...t, lead_key: null } : t));
  return { ...draft, teams, teamOf: { ...draft.teamOf, [key]: teamId } };
}

export function removeTeam(draft: Draft, teamId: string): Draft {
  const teamOf = Object.fromEntries(Object.entries(draft.teamOf).map(([k, v]) => [k, v === teamId ? null : v]));
  return { ...draft, teams: draft.teams.filter((t) => t.id !== teamId), teamOf };
}

/** Tidy tree, top to bottom: each level is a row, leaves spread evenly, parents centred over their children. Percent of the stage. */
export function treeLayout(agents: StructureAgent[], parents: Record<string, string | null>, manual: Draft["pos"] = {}): Map<string, Spot> {
  const keys = agents.map((a) => a.key);
  const children = new Map<string, string[]>();
  for (const key of keys) {
    if (key === CHIEF) continue;
    const parent = parents[key] ?? CHIEF;
    children.set(parent, [...(children.get(parent) ?? []), key]);
  }
  const depth = new Map<string, number>([[CHIEF, 0]]);
  const x = new Map<string, number>();
  let leaf = 0;
  const leaves = keys.filter((k) => k !== CHIEF && !children.has(k)).length || 1;
  const walk = (key: string, level: number) => {
    depth.set(key, level);
    const kids = children.get(key) ?? [];
    if (!kids.length) {
      x.set(key, leaf++);
      return;
    }
    kids.forEach((kid) => walk(kid, level + 1));
    x.set(key, (x.get(kids[0]!)! + x.get(kids[kids.length - 1]!)!) / 2);
  };
  walk(CHIEF, 0);
  const levels = Math.max(...depth.values());
  const spots = new Map<string, Spot>();
  for (const key of keys) {
    if (!x.has(key)) continue;
    const column = leaves === 1 ? 0.5 : x.get(key)! / (leaves - 1);
    const spot = { x: 10 + column * 80, y: levels === 0 ? 50 : 14 + (depth.get(key)! / levels) * 72 };
    spots.set(key, manual[key] ?? spot);
  }
  return spots;
}

/** The frame of a team: the box around its members' spots, with padding, in percent. */
export function teamFrame(members: Spot[]): { x: number; y: number; w: number; h: number } | null {
  if (!members.length) return null;
  const xs = members.map((m) => m.x);
  const ys = members.map((m) => m.y);
  const pad = { x: 7, y: 9 };
  const left = Math.max(1, Math.min(...xs) - pad.x);
  const top = Math.max(1, Math.min(...ys) - pad.y);
  return { x: left, y: top, w: Math.min(99, Math.max(...xs) + pad.x) - left, h: Math.min(99, Math.max(...ys) + pad.y) - top };
}

export type StructurePayload = {
  teams: StructureTeam[];
  agents: { key: string; reports_to: string | null; team_id: string | null; map_x: number | null; map_y: number | null }[];
};

export function payloadOf(draft: Draft, agents: StructureAgent[]): StructurePayload {
  return {
    teams: draft.teams,
    agents: agents
      .filter((a) => a.key === CHIEF || connectable(a) || draft.parents[a.key] === null)
      .map((a) => {
        const parent = a.key === CHIEF ? null : (draft.parents[a.key] ?? CHIEF);
        return {
          key: a.key,
          // The default (under the chief) is stored as nothing, so the shape stays "never edited".
          reports_to: parent === CHIEF ? null : parent,
          team_id: draft.teamOf[a.key] ?? null,
          map_x: draft.pos[a.key]?.x ?? null,
          map_y: draft.pos[a.key]?.y ?? null,
        };
      }),
  };
}
