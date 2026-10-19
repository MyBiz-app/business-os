"""The legal and accountant agents (slice C3b): the "not advice" notice, the country a question is
about, and the guides their libraries start with.

The notice is added by the server to every answer of these two agents, in the language of the
question, so it never depends on the model remembering to write it."""

import re
from pathlib import Path

PROFESSIONAL_ROLES = frozenset({"legal", "accountant"})
COUNTRIES = {"IL": "Israel", "US": "United States"}
DEFAULT_COUNTRY = "IL"  # MyBiz itself is an Israeli company

GUIDES = Path(__file__).parent / "guides"

_NOTICE = {
    ("legal", "he"): "זו טיוטה ולא ייעוץ משפטי. יש לבדוק אותה עם עורך דין.",
    ("legal", "en"): "This is a draft, not legal advice. Check it with a lawyer.",
    ("accountant", "he"): "זו טיוטה ולא ייעוץ חשבונאי או מס. יש לבדוק אותה עם רואה חשבון.",
    (
        "accountant",
        "en",
    ): "This is a draft, not accounting or tax advice. Check it with an accountant.",
}
_HEBREW = re.compile("[֐-׿]")


def notice_for(role: str, question: str) -> str | None:
    """The fixed line for the agent's answer, or None when the agent is not one of the two."""
    if role not in PROFESSIONAL_ROLES:
        return None
    return _NOTICE[(role, "he" if _HEBREW.search(question) else "en")]


def with_notice(role: str, question: str, answer: str) -> str:
    notice = notice_for(role, question)
    if notice is None or notice in answer:
        return answer
    return f"{answer.rstrip()}\n\n{notice}" if answer.strip() else notice


def country_of(currency: str | None) -> str | None:
    """The country a business gets when it is created: by its currency (as migration 0149 does)."""
    return {"ILS": "IL", "USD": "US"}.get(currency or "")


def guide(name: str) -> str:
    return (GUIDES / f"{name}.md").read_text(encoding="utf-8")
