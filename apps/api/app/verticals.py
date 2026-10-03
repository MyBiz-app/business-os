"""Vertical packs: configuration that adapts the vertical-agnostic core to an industry.

The core never branches on the vertical; it reads the pack. Packs grow with each sprint
(terminology, default services, roles, metrics)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class VerticalPack:
    key: str
    client_term: str  # i18n key suffix for what the business calls its clients
    cancellation_window_minutes: int  # default booking policy for new businesses


VERTICAL_PACKS: dict[str, VerticalPack] = {
    "fitness": VerticalPack(key="fitness", client_term="member", cancellation_window_minutes=120),
}
