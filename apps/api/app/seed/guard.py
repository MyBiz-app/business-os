"""Accounts the demo seed must never fill or tidy.

The MyBiz primary owner owns no businesses (it lands in the console), and `curated` removes the
other businesses its account owns alone. So the seed refuses these emails for every demo except
`platform`, which only turns the account into a platform team owner. The list is fixed in code
and can be extended with the `API_SEED_BLOCKED_EMAILS` environment variable (comma separated).
"""

import os
import sys

BLOCKED_OWNERS = frozenset({"adire7399@gmail.com"})
ENV_VAR = "API_SEED_BLOCKED_EMAILS"


def blocked_owners() -> frozenset[str]:
    extra = {e.strip().lower() for e in os.environ.get(ENV_VAR, "").split(",") if e.strip()}
    return BLOCKED_OWNERS | extra


def refuse_blocked_owner(email: str) -> None:
    """Stops the program (SystemExit) when the account must not get demo businesses."""
    if email.strip().lower() in blocked_owners():
        sys.exit(
            f"Refusing to seed demo businesses for {email}: this account is the MyBiz primary "
            "owner and must own no businesses. Use the demo account instead."
        )
