"""Error monitoring (Sentry), off unless `API_SENTRY_DSN` is set.

Privacy first: no personal data is sent. Request bodies, cookies, headers, query strings and
user details are stripped before an event leaves the process; only the route template, the
request id and the tenant id travel with the error."""

import os
from typing import Any

from app.core.config import Settings

_enabled = False


def monitoring_enabled() -> bool:
    return _enabled


def scrub_event(event: dict[str, Any], _hint: object = None) -> dict[str, Any]:
    """Drop everything about the request except what helps find the bug."""
    request = event.get("request")
    if isinstance(request, dict):
        event["request"] = {
            "method": request.get("method"),
            "url": str(request.get("url", "")).split("?", 1)[0],
        }
    event.pop("user", None)
    return event


def init_monitoring(settings: Settings) -> bool:
    """Start Sentry when a DSN is configured. Returns whether monitoring is on."""
    global _enabled
    if settings.sentry_dsn is None:
        return False
    import sentry_sdk  # imported lazily: nothing is loaded while monitoring is off

    sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        environment=settings.environment,
        release=settings.sentry_release or os.environ.get("RENDER_GIT_COMMIT") or None,
        send_default_pii=False,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        max_request_body_size="never",
        before_send=scrub_event,
    )
    _enabled = True
    return True


def capture_exception(
    error: BaseException, request_id: str | None = None, tenant_id: str | None = None
) -> None:
    """Report a handled-by-middleware crash, tagged with the ids that are also in the logs."""
    if not _enabled:
        return
    import sentry_sdk

    with sentry_sdk.new_scope() as scope:
        scope.set_tag("request_id", request_id)
        scope.set_tag("tenant_id", tenant_id)
        sentry_sdk.capture_exception(error)
