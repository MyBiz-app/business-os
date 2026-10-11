"""The monthly AI allowance: what the business has used this calendar month (in its time zone)
against what its AI module includes. Soft limit: questions stop at 100%, nothing else does."""

from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.commerce.modules import ai_credits_allowed


def credits_used(db: Session, month_start: date) -> float:
    return float(
        db.execute(
            text("""
                SELECT coalesce(sum(u.quantity), 0) FROM app.usage_events u
                JOIN app.tenants t ON t.id = u.tenant_id
                WHERE u.meter = 'ai_credits' AND t.id = app.current_tenant_id()
                  AND u.occurred_at >= (CAST(:start AS date)::timestamp AT TIME ZONE t.time_zone)
            """),
            {"start": month_start},
        ).scalar_one()
    )


def credits_included(db: Session) -> int:
    modules = db.execute(text("SELECT module_key FROM app.tenant_modules")).scalars().all()
    return ai_credits_allowed(list(modules))
