"""The words a business may rename ("clients" to "club members"). The screens read these from
`terms.<set>` in the translations; the list here is the part an owner can change. Words with a
count in them (`sessionsToday`) are not renameable, because their grammar changes with the
number. A test keeps this list equal to the translated words."""

from typing import Any

TERM_KEYS: tuple[str, ...] = (
    "client",
    "clients",
    "addClient",
    "newClient",
    "searchClients",
    "noClients",
    "noResults",
    "schedule",
    "newSession",
    "noSessions",
    "appTab",
    "appEmpty",
    "place",
    "profile",
    "visitNotes",
    "nextBooking",
)

LOCALES = ("he", "en")
MAX_TERM_LENGTH = 60


def clean_terms_override(raw: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """The saved shape: known languages and words only, trimmed, empty ones dropped.
    Raises ValueError with the reason for an unknown language, an unknown word or a long text."""
    cleaned: dict[str, Any] = {}
    for locale, words in raw.items():
        if locale not in LOCALES:
            raise ValueError("unknown_locale")
        kept: dict[str, str] = {}
        for key, value in words.items():
            if key not in TERM_KEYS:
                raise ValueError("unknown_term")
            text = " ".join(value.split())
            if len(text) > MAX_TERM_LENGTH:
                raise ValueError("term_too_long")
            if text:
                kept[key] = text
        if kept:
            cleaned[locale] = kept
    return cleaned
