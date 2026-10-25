"""Accounts the demo seed must never fill or tidy.

The list is empty in code (the MyBiz primary owner, adire7399, may own a demo studio and train
in it, decision of 2026-10-25) and can be filled with the `API_SEED_BLOCKED_EMAILS` environment
variable (comma separated). The seed refuses those emails for every demo except `platform`.
"""

import os
import sys

BLOCKED_OWNERS: frozenset[str] = frozenset()
ENV_VAR = "API_SEED_BLOCKED_EMAILS"


def blocked_owners() -> frozenset[str]:
    extra = {e.strip().lower() for e in os.environ.get(ENV_VAR, "").split(",") if e.strip()}
    return BLOCKED_OWNERS | extra


def refuse_blocked_owner(email: str) -> None:
    """Stops the program (SystemExit) when the account must not get demo businesses."""
    if email.strip().lower() in blocked_owners():
        sys.exit(
            f"Refusing to seed demo businesses for {email}: the account is listed in "
            f"{ENV_VAR}. Use the demo account instead."
        )
