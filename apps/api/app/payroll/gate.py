"""Who may run payroll (round 6, P4 and K2): the business has the payroll module, and the legal
details a payroll needs (business number, address, employer file number) are filled in. Checked on
the server for every change to a run; looking at existing runs and payslips stays open."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import TenantContext, has_module, require
from app.core.legal_readiness import evaluate
from app.core.permissions import Permission


def ensure_payroll_open(session: Session) -> None:
    """Raises 403 `module_disabled` without the payroll module and 409 `payroll_details_missing`
    while the readiness card still lacks something payroll needs."""
    if not has_module(session, "payroll"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="module_disabled")
    tenant = (
        session.execute(
            text("""
                SELECT currency, legal_entity_type, business_number, address_line, address_city,
                       employer_file_number, business_license_number,
                       business_license_expires_on,
                       (now() AT TIME ZONE time_zone)::date AS today
                FROM app.tenants WHERE id = app.current_tenant_id()
            """)
        )
        .mappings()
        .one()
    )
    readiness = evaluate(
        currency=tenant["currency"],
        entity_type=tenant["legal_entity_type"],
        business_number=tenant["business_number"],
        address_line=tenant["address_line"],
        address_city=tenant["address_city"],
        employer_file=tenant["employer_file_number"],
        license_number=tenant["business_license_number"],
        license_expires_on=tenant["business_license_expires_on"],
        today=tenant["today"],
    )
    if not readiness.payroll:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="payroll_details_missing")


def require_open(permission: Permission) -> Callable[[TenantContext], TenantContext]:
    """Like `require`, and the business must also be allowed to run payroll."""
    base = require(permission)

    def check(context: Annotated[TenantContext, Depends(base)]) -> TenantContext:
        ensure_payroll_open(context.session)
        return context

    return check
