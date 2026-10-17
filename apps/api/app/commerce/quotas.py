"""Plan quota alerts (go-live, GL21): the 80% and 100% marks of a month's messages and space.

The alerts only tell the owner (the CRM shows them with the usage). Nothing stops here: messages
keep going and uploads stop at the space allowance in app/files, as the owner decided (#104)."""

import datetime as dt
from typing import Final

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

THRESHOLDS: Final = (80, 100)
METERS: Final = ("messages", "storage")


class QuotaAlert(BaseModel):
    meter: str = Field(description="messages or storage")
    threshold: int = Field(description="Percent of the bundle passed: 80 or 100")


def raise_alerts(
    db: Session, month_start: dt.date, used: dict[str, int], included: dict[str, int]
) -> None:
    """Records, once a month, each threshold a meter passed. A meter with no bundle is skipped."""
    for meter in METERS:
        if included[meter] <= 0:
            continue
        percent = used[meter] * 100 / included[meter]
        for threshold in THRESHOLDS:
            if percent < threshold:
                break
            db.execute(
                text("""
                    INSERT INTO app.quota_alerts (tenant_id, meter, month_start, threshold)
                    VALUES (app.current_tenant_id(), :meter, :month, :threshold)
                    ON CONFLICT DO NOTHING
                """),
                {"meter": meter, "month": month_start, "threshold": threshold},
            )


def month_alerts(db: Session, month_start: dt.date) -> list[QuotaAlert]:
    rows = db.execute(
        text("""
            SELECT meter, threshold FROM app.quota_alerts
            WHERE month_start = :month ORDER BY meter, threshold
        """),
        {"month": month_start},
    ).all()
    return [QuotaAlert(meter=meter, threshold=threshold) for meter, threshold in rows]
