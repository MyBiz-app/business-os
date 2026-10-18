"""The cancellation policy a new business starts with, by category (round 7, R32).

Minutes before the session that a client may cancel for free, for a group class, a personal
session (a trainer, a treatment, an appointment) and a court or room, and what a late
cancellation and a no-show count as. The business changes them in its first setup step.
A category not listed here uses `DEFAULT`."""

from dataclasses import dataclass

HOUR = 60


@dataclass(frozen=True)
class CancellationDefaults:
    group_minutes: int
    personal_minutes: int
    resource_minutes: int
    late_outcome: str  # "counts" (a used visit) | "recorded" (only noted) | "fee" (kept off)
    no_show_outcome: str


_STRICT = CancellationDefaults(6 * HOUR, 24 * HOUR, 24 * HOUR, "counts", "counts")

DEFAULT = CancellationDefaults(2 * HOUR, 12 * HOUR, 12 * HOUR, "recorded", "recorded")

BY_CATEGORY: dict[str, CancellationDefaults] = {
    "fitness": _STRICT,
    "classes": _STRICT,  # dance, martial arts, music: class-based like a studio
    "sports": _STRICT,
    # Appointments only: the group window is never used, so it follows the personal one.
    "beauty": CancellationDefaults(24 * HOUR, 24 * HOUR, 24 * HOUR, "counts", "counts"),
    "clinic": CancellationDefaults(24 * HOUR, 24 * HOUR, 24 * HOUR, "counts", "counts"),
}


def defaults_for(category: str) -> CancellationDefaults:
    return BY_CATEGORY.get(category, DEFAULT)
