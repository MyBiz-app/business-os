import type { Role } from "@/lib/api";

// Mirrors apps/api/app/permissions.py so the UI hides what the API would refuse.
// The API remains the authority; this only avoids showing dead buttons.
const CLIENT_WRITERS = new Set<Role>(["owner", "manager", "front_desk"]);
const CATALOG_WRITERS = new Set<Role>(["owner", "manager"]);

export function canWriteClients(role: Role): boolean {
  return CLIENT_WRITERS.has(role);
}

export function canWriteCatalog(role: Role): boolean {
  return CATALOG_WRITERS.has(role);
}

const TEAM_MANAGERS = new Set<Role>(["owner", "manager"]);

export function canManageTeam(role: Role): boolean {
  return TEAM_MANAGERS.has(role);
}
