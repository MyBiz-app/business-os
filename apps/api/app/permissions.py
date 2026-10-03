"""Permissions are fine-grained keys defined in code; roles are named bundles of them.

System roles are fixed for now. Custom roles per business (a toggle UI over these keys)
come later and will be stored in the database."""

from enum import StrEnum


class Permission(StrEnum):
    CLIENTS_READ = "clients.read"
    CLIENTS_WRITE = "clients.write"
    BUSINESS_SETTINGS = "business.settings"


ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "owner": frozenset(Permission),
    "manager": frozenset(
        {
            Permission.CLIENTS_READ,
            Permission.CLIENTS_WRITE,
            Permission.BUSINESS_SETTINGS,
        }
    ),
    "front_desk": frozenset({Permission.CLIENTS_READ, Permission.CLIENTS_WRITE}),
    "staff": frozenset({Permission.CLIENTS_READ}),
}


def role_allows(role: str, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())
