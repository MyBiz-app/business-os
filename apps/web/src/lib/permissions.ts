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

export function canManageSettings(role: Role): boolean {
  return TEAM_MANAGERS.has(role);
}

const SCHEDULE_WRITERS = new Set<Role>(["owner", "manager", "front_desk"]);

export function canWriteSchedule(role: Role): boolean {
  return SCHEDULE_WRITERS.has(role);
}

// Instructors (staff) check members in to their classes, so every role can manage bookings.
const BOOKING_MANAGERS = new Set<Role>(["owner", "manager", "front_desk", "staff"]);

export function canManageBookings(role: Role): boolean {
  return BOOKING_MANAGERS.has(role);
}

const SELLERS = new Set<Role>(["owner", "manager", "front_desk"]);

export function canSell(role: Role): boolean {
  return SELLERS.has(role);
}

const REPORT_READERS = new Set<Role>(["owner", "manager"]);

export function canReadReports(role: Role): boolean {
  return REPORT_READERS.has(role);
}
