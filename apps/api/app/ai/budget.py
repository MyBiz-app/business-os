"""The monthly AI allowance: what the business has used this calendar month (in its time zone)
against what its AI module includes, plus the business's own spend controls.

Soft limit: questions stop at the limit, nothing else does. The limit is the included credits,
or, when pay-as-you-go is on, the included credits plus the extra the business agreed to (its cap;
no cap means no limit). A role or a person can also have a lower monthly limit."""

import datetime as dt
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.commerce.modules import ai_credits_allowed, ai_extra_price

# Used / included, in percent: each is raised once a month as an alert in the CRM.
ALERT_THRESHOLDS = (80, 100, 150, 200)


def credits_used(db: Session, month_start: dt.date) -> float:
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


@dataclass(frozen=True)
class Spend:
    payg_enabled: bool
    payg_cap_minor: int | None  # None: no cap
    currency: str

    @property
    def price_per_100(self) -> int:
        return ai_extra_price(self.currency)

    def cap_credits(self) -> int | None:
        """The extra credits the cap pays for (None: unlimited)."""
        if self.payg_cap_minor is None:
            return None
        return self.payg_cap_minor * 100 // self.price_per_100

    def extra_minor(self, used: float, included: int) -> int:
        """What the use above the included credits costs, in minor units."""
        return round(max(used - included, 0) * self.price_per_100 / 100)


def spend_settings(db: Session) -> Spend:
    row = db.execute(
        text("""
            SELECT coalesce(s.payg_enabled, false) AS payg_enabled, s.payg_cap_minor, t.currency
            FROM app.tenants t
            LEFT JOIN app.tenant_ai_settings s ON s.tenant_id = t.id
            WHERE t.id = app.current_tenant_id()
        """)
    ).one()
    return Spend(row.payg_enabled, row.payg_cap_minor, row.currency)


def credits_limit(db: Session) -> int | None:
    """Credits the business may use this month (None: no limit, pay-as-you-go without a cap).
    A business with no AI module has none, whatever it set."""
    included = credits_included(db)
    if included == 0:
        return 0
    spend = spend_settings(db)
    if not spend.payg_enabled:
        return included
    extra = spend.cap_credits()
    return None if extra is None else included + extra


def over_limit(db: Session, month_start: dt.date) -> bool:
    limit = credits_limit(db)
    return limit is not None and credits_used(db, month_start) >= limit


def person_limit(db: Session, user_id: UUID, role_keys: frozenset[str]) -> int | None:
    """The lowest monthly limit set for the person, or for any role they hold."""
    rows = db.execute(
        text("""
            SELECT monthly_credits FROM app.ai_credit_limits
            WHERE (subject_kind = 'user' AND subject_key = :user)
               OR (subject_kind = 'role' AND subject_key = ANY(:roles))
        """),
        {"user": str(user_id), "roles": sorted(role_keys)},
    ).scalars()
    return min(rows, default=None)


def person_used(db: Session, user_id: UUID, month_start: dt.date) -> float:
    return float(
        db.execute(
            text("""
                SELECT coalesce(sum(u.quantity), 0) FROM app.usage_events u
                JOIN app.tenants t ON t.id = u.tenant_id
                WHERE u.meter = 'ai_credits' AND t.id = app.current_tenant_id()
                  AND u.details ->> 'user_id' = :user
                  AND u.occurred_at >= (CAST(:start AS date)::timestamp AT TIME ZONE t.time_zone)
            """),
            {"start": month_start, "user": str(user_id)},
        ).scalar_one()
    )


def over_person_limit(
    db: Session, user_id: UUID, role_keys: frozenset[str], month_start: dt.date
) -> bool:
    limit = person_limit(db, user_id, role_keys)
    return limit is not None and person_used(db, user_id, month_start) >= limit


def raise_alerts(db: Session, month_start: dt.date) -> list[int]:
    """Records the thresholds the month's use has passed and had not raised yet; returns them."""
    included = credits_included(db)
    if included == 0:
        return []
    percent = credits_used(db, month_start) * 100 / included
    new = []
    for threshold in ALERT_THRESHOLDS:
        if percent < threshold:
            break
        inserted = db.execute(
            text("""
                INSERT INTO app.ai_credit_alerts (tenant_id, month_start, threshold)
                VALUES (app.current_tenant_id(), :month, :threshold)
                ON CONFLICT DO NOTHING RETURNING threshold
            """),
            {"month": month_start, "threshold": threshold},
        ).scalar_one_or_none()
        if inserted is not None:
            new.append(threshold)
    return new
