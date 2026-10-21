"""Web search for console agents (slice C4). It costs money (about $10 per 1,000 searches), so it
is OFF until the team switches it on, and then limited to a number of searches per calendar month.
Only providers that can run the search on their side offer it; the demo and the other vendors
never do."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.ai.gateway import LLMProvider

# The roles that may search the web. The market researcher needs competitor prices; no other
# agent gets it.
ROLES = frozenset({"market"})
MAX_PER_QUESTION = 8
MAX_MONTHLY_LIMIT = 1000


@dataclass(frozen=True)
class WebSearch:
    enabled: bool
    monthly_limit: int
    used_this_month: int

    @property
    def remaining(self) -> int:
        return max(self.monthly_limit - self.used_this_month, 0) if self.enabled else 0


def state(db: Session) -> WebSearch:
    row = db.execute(text("SELECT * FROM app.platform_ai_web_search_get()")).one()
    return WebSearch(row.enabled, row.monthly_limit, row.used_this_month)


def tool_for(db: Session, provider: LLMProvider, role: str) -> dict[str, Any] | None:
    """The search tool to offer on this question, or None (off, no budget left, wrong role or a
    provider that cannot run it)."""
    if role not in ROLES or not getattr(provider, "supports_web_search", False):
        return None
    left = state(db).remaining
    if left <= 0:
        return None
    return {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": min(left, MAX_PER_QUESTION),
    }
