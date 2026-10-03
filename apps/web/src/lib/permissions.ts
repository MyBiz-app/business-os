import type { Role } from "@/lib/api";

// Mirrors apps/api/app/permissions.py so the UI hides what the API would refuse.
// The API remains the authority; this only avoids showing dead buttons.
const CLIENT_WRITERS = new Set<Role>(["owner", "manager", "front_desk"]);

export function canWriteClients(role: Role): boolean {
  return CLIENT_WRITERS.has(role);
}
