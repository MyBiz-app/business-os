"""The payroll bureau adapter (round 6, P5): switched off.

A paid payroll service would take the month's pay data and work out net pay and payslips itself.
Until the business operates only the interface exists: it is not registered as a provider choice,
so no business can switch it on, and MyBiz's own calculation (`app.payroll.net`) stays the only
path. Adding a real adapter later means implementing this protocol and registering it."""

from typing import Protocol


class PayrollProvider(Protocol):
    def submit_run(self, tenant_id: str, period: str, lines: list[dict]) -> str:
        """Sends a locked month to the bureau; returns the bureau's reference."""
        ...


class PayrollUnavailable(RuntimeError):
    """Raised for any attempt to use a payroll bureau: none is connected."""


class DisabledPayroll:
    def submit_run(self, tenant_id: str, period: str, lines: list[dict]) -> str:
        raise PayrollUnavailable("no payroll bureau is connected")
