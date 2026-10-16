"""What a business has told us about itself legally, and what each missing piece would hold up.

Nothing here blocks the product: a missing piece only switches off the one action that needs
it (issuing a tax invoice, running payroll). The business licence is always optional; its
expiry is only reminded (LICENSE_REMINDER_DAYS ahead)."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel

LICENSE_REMINDER_DAYS = 60
# Israeli companies (ח.פ.) are registered under numbers starting with 51.
COMPANY_PREFIX = "51"

Check = Literal["entity_type", "business_number", "address", "employer_file", "license"]
LicenseStatus = Literal["none", "valid", "expiring", "expired"]


class ReadinessItem(BaseModel):
    key: Check
    done: bool
    optional: bool
    unlocks: Literal["tax_invoice", "payroll"] | None
    warning: Literal["company_prefix"] | None = None


class Readiness(BaseModel):
    items: list[ReadinessItem]
    license_status: LicenseStatus
    license_days_left: int | None
    tax_invoice: bool
    receipts_only: bool
    payroll: bool


def license_status(
    expires_on: dt.date | None, today: dt.date, has_license: bool
) -> tuple[LicenseStatus, int | None]:
    if not has_license and expires_on is None:
        return "none", None
    if expires_on is None:
        return "valid", None
    days = (expires_on - today).days
    if days < 0:
        return "expired", days
    return ("expiring" if days <= LICENSE_REMINDER_DAYS else "valid"), days


def evaluate(
    *,
    currency: str,
    entity_type: str | None,
    business_number: str | None,
    address_line: str | None,
    address_city: str | None,
    employer_file: str | None,
    license_number: str | None,
    license_expires_on: dt.date | None,
    today: dt.date,
) -> Readiness:
    has_address = bool(address_line and address_city)
    prefix_warning = (
        entity_type == "company"
        and currency == "ILS"
        and bool(business_number)
        and not (business_number or "").startswith(COMPANY_PREFIX)
    )
    status, days = license_status(license_expires_on, today, bool(license_number))
    base = bool(entity_type and business_number)
    items = [
        ReadinessItem(key="entity_type", done=bool(entity_type), optional=False, unlocks=None),
        ReadinessItem(
            key="business_number",
            done=bool(business_number),
            optional=False,
            unlocks=None,
            warning="company_prefix" if prefix_warning else None,
        ),
        ReadinessItem(key="address", done=has_address, optional=False, unlocks="tax_invoice"),
        ReadinessItem(
            key="employer_file", done=bool(employer_file), optional=False, unlocks="payroll"
        ),
        ReadinessItem(key="license", done=status != "none", optional=True, unlocks=None),
    ]
    # An exempt dealer (עוסק פטור) issues receipts, never a tax invoice.
    receipts_only = entity_type == "exempt_dealer"
    return Readiness(
        items=items,
        license_status=status,
        license_days_left=days,
        tax_invoice=base and has_address and not receipts_only,
        receipts_only=receipts_only,
        payroll=base and has_address and bool(employer_file),
    )
