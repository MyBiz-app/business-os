from app.core.permissions import ROLE_PERMISSIONS, Permission

# The full matrix, written out so that any change to who-can-do-what is a visible diff.
EXPECTED = {
    "owner": set(Permission),
    "manager": set(Permission) - {"clients.privacy"},
    "front_desk": {
        "clients.read",
        "clients.write",
        "catalog.read",
        "schedule.read",
        "schedule.write",
        "bookings.manage",
        "sales.manage",
        "ai.use",
    },
    "staff": {"clients.read", "catalog.read", "schedule.read", "bookings.manage"},
}


def test_role_permission_matrix() -> None:
    assert {role: set(keys) for role, keys in ROLE_PERMISSIONS.items()} == EXPECTED
