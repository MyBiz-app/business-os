import type { Tenant } from "@/lib/api";

// The API sends the user's effective permissions (their custom role's switches, or the system
// role's bundle). The UI only hides what the API would refuse; the API remains the authority.
type Access = Pick<Tenant, "permissions">;

const has = (tenant: Access, permission: string) => tenant.permissions.includes(permission);

export const canWriteClients = (tenant: Access) => has(tenant, "clients.write");
export const canWriteCatalog = (tenant: Access) => has(tenant, "catalog.write");
export const canWriteSchedule = (tenant: Access) => has(tenant, "schedule.write");
export const canManageBookings = (tenant: Access) => has(tenant, "bookings.manage");
export const canSell = (tenant: Access) => has(tenant, "sales.manage");
export const canReadReports = (tenant: Access) => has(tenant, "reports.read");
export const canUseAssistant = (tenant: Access) => has(tenant, "ai.use");
/** The team and its roles (viewing needs `staff.read`, changing needs `staff.manage`). */
export const canManageTeam = (tenant: Access) => has(tenant, "staff.manage");
export const canManageSettings = (tenant: Access) => has(tenant, "business.settings");
