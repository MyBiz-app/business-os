"""Permissions are fine-grained keys defined in code; roles are named bundles of them.

System roles are fixed for now. Custom roles per business (a toggle UI over these keys)
come later and will be stored in the database."""

from enum import StrEnum


class Permission(StrEnum):
    CLIENTS_READ = "clients.read"
    CLIENTS_WRITE = "clients.write"
    CATALOG_READ = "catalog.read"
    CATALOG_WRITE = "catalog.write"
    SCHEDULE_READ = "schedule.read"
    SCHEDULE_WRITE = "schedule.write"
    BOOKINGS_MANAGE = "bookings.manage"  # book clients into sessions, check in, cancel
    STAFF_READ = "staff.read"
    STAFF_MANAGE = "staff.manage"
    BUSINESS_SETTINGS = "business.settings"


ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "owner": frozenset(Permission),
    "manager": frozenset(
        {
            Permission.CLIENTS_READ,
            Permission.CLIENTS_WRITE,
            Permission.CATALOG_READ,
            Permission.CATALOG_WRITE,
            Permission.SCHEDULE_READ,
            Permission.SCHEDULE_WRITE,
            Permission.BOOKINGS_MANAGE,
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


def role_allows(role: str, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())
