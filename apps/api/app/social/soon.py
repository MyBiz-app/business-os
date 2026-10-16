"""Adapters for the networks that are not open yet (shown as "coming soon").

Each is registered but disabled: it cannot be connected until its access is arranged (X's API is
paid, LinkedIn and Snapchat need a partner approval, Pinterest comes in a later round). To open
one, replace its class with a real connector in its own file and keep the same `name`."""

from datetime import date, datetime

from app.social.providers import AccountInfo, AudienceSlice, DayMetrics, PostData, register_social


class DisabledProvider:
    """A connector that is wired in but switched off."""

    callback = "disabled"

    def __init__(self, name: str) -> None:
        self.name = name

    def configured(self) -> bool:
        return False

    def authorize_url(self, state: str, redirect_uri: str) -> str:
        raise NotImplementedError(f"{self.name} is not open yet")

    def exchange_code(self, code: str, redirect_uri: str) -> list[AccountInfo]:
        raise NotImplementedError(f"{self.name} is not open yet")

    def refresh(self, secrets: dict[str, str]) -> dict[str, str]:
        return secrets

    def fetch_account_metrics(
        self, account: AccountInfo, since: date, until: date
    ) -> list[DayMetrics]:
        return []

    def fetch_posts(self, account: AccountInfo, since: datetime) -> list[PostData]:
        return []

    def fetch_audience(self, account: AccountInfo) -> list[AudienceSlice]:
        return []


for _name in ("x", "linkedin", "pinterest", "snapchat"):
    register_social(DisabledProvider(_name))
