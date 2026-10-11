"""Invoicing: issuing the legal document for a payment (a receipt / tax invoice-receipt).

Every payment gets a receipt in MyBiz with its own running number. A business that connects an
invoicing provider has each receipt issued there as well; the provider's document number and
link are kept on the receipt. The built-in `internal` provider keeps MyBiz's receipt as the
document."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.providers.registry import register


@dataclass(frozen=True)
class DocumentLine:
    description: str
    quantity: float
    unit_price: int  # minor units


@dataclass(frozen=True)
class InvoiceDocument:
    """A receipt to issue, in the system's words."""

    receipt_id: str  # our id: providers use it to avoid issuing twice
    receipt_number: int
    issued_at: datetime
    business_name: str
    client_name: str
    client_email: str | None
    lines: tuple[DocumentLine, ...]
    total: int  # minor units
    currency: str
    payment_method: str  # card | cash | transfer | other
    locale: str = "he"


@dataclass(frozen=True)
class IssuedDocument:
    number: str | None  # the provider's document number; None: no separate document
    url: str | None  # a link to the document (PDF), if the provider gives one
    provider_ref: str | None


class InvoiceProvider(Protocol):
    def issue(self, document: InvoiceDocument) -> IssuedDocument: ...


class InvoicingUnavailable(RuntimeError):
    """The provider refused or could not be reached (the job tries again later)."""


@register(
    "invoicing",
    "internal",
    "MyBiz receipts",
    builtin=True,
    description="MyBiz numbers and keeps the receipts; no outside invoicing account.",
)
class InternalReceipts:
    def __init__(self, settings: dict[str, str]) -> None:
        self.settings = settings

    def issue(self, document: InvoiceDocument) -> IssuedDocument:
        return IssuedDocument(number=None, url=None, provider_ref=None)
