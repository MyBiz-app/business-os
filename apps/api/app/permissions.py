"""Permissions are fine-grained keys defined in code; roles are named bundles of them.

System roles are fixed bundles. A business can also define custom roles (switches over these
keys, stored in app.tenant_roles); a member with a custom role has exactly its permissions."""

from enum import StrEnum


class Permission(StrEnum):
    CLIENTS_READ = "clients.read"
    CLIENTS_WRITE = "clients.write"
    CLIENTS_PRIVACY = "clients.privacy"  # export or erase a client's personal data (owners)
    CATALOG_READ = "catalog.read"
    CATALOG_WRITE = "catalog.write"
    SCHEDULE_READ = "schedule.read"
    SCHEDULE_WRITE = "schedule.write"
    BOOKINGS_MANAGE = "bookings.manage"  # book clients into sessions, check in, cancel
    SALES_MANAGE = "sales.manage"  # sell, freeze and cancel clients' plans
    REPORTS_READ = "reports.read"  # business KPIs (revenue, occupancy, ...)
    AI_USE = "ai.use"  # the AI assistant (its tools still check the permissions above)
    STAFF_READ = "staff.read"
    STAFF_MANAGE = "staff.manage"
    BUSINESS_SETTINGS = "business.settings"


ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "owner": frozenset(Permission),
    "manager": frozenset(
        {  # everything except privacy requests
            Permission.CLIENTS_READ,
            Permission.CLIENTS_WRITE,
            Permission.CATALOG_READ,
            Permission.CATALOG_WRITE,
            Permission.SCHEDULE_READ,
            Permission.SCHEDULE_WRITE,
            Permission.BOOKINGS_MANAGE,
            Permission.SALES_MANAGE,
            Permission.REPORTS_READ,
            Permission.AI_USE,
            Permission.STAFF_READ,
            Permission.STAFF_MANAGE,
            Permission.BUSINESS_SETTINGS,
        }
    ),
    "front_desk": frozenset(
        {
            Permission.CLIENTS_READ,
            Permission.CLIENTS_WRITE,
            Permission.CATALOG_READ,
            Permission.SCHEDULE_READ,
            Permission.SCHEDULE_WRITE,
            Permission.BOOKINGS_MANAGE,
            Permission.SALES_MANAGE,
            Permission.AI_USE,
        }
    ),
    "staff": frozenset(
        {
            Permission.CLIENTS_READ,
            Permission.CATALOG_READ,
            Permission.SCHEDULE_READ,
            # Instructors check members in to their own classes.
            Permission.BOOKINGS_MANAGE,
        }
    ),
}


# Platform support inside a business that granted access: read-only, never settings or AI.
SUPPORT_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.CLIENTS_READ,
        Permission.CATALOG_READ,
        Permission.SCHEDULE_READ,
        Permission.REPORTS_READ,
        Permission.STAFF_READ,
    }
)


def effective_permissions(role: str, custom: list[str] | None) -> frozenset[str]:
    """The permissions a member actually has. Owners always have everything."""
    if role == "support":
        return frozenset(p.value for p in SUPPORT_PERMISSIONS)
    if custom is not None and role != "owner":
        known = {p.value for p in Permission}
        return frozenset(p for p in custom if p in known)
    return frozenset(p.value for p in ROLE_PERMISSIONS.get(role, frozenset()))
