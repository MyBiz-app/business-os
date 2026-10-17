"""The rules of the documents a business issues: which kinds exist, who may issue them, and the
VAT and allocation-number arithmetic. Pure functions, no database."""

from typing import Final, Literal

Kind = Literal["tax_invoice_receipt", "tax_invoice", "credit_note", "quote", "transaction_invoice"]

# The kinds an exempt dealer (עוסק פטור) never issues: they need a licensed dealer or company.
TAX_KINDS: Final[frozenset[str]] = frozenset({"tax_invoice_receipt", "tax_invoice", "credit_note"})
# Kinds that print the VAT breakdown. A quote and a transaction invoice show the total only.
VAT_KINDS: Final[frozenset[str]] = TAX_KINDS

FIRST_NUMBER: Final = 1001  # every series starts here, like the receipts (migration 0105)
VAT_RATE_BP: Final = 1800  # 18%, in basis points
# A tax invoice whose amount before VAT is above this needs an allocation number from the tax
# authority (a number the invoicing provider fetches, #47). Minor units (ILS 5,000 from 2026).
# The threshold keeps dropping year by year: this is the one place to change it.
ALLOCATION_THRESHOLD: Final = 500_000


def vat_rate_bp(entity_type: str | None) -> int:
    """Exempt dealers charge no VAT."""
    return 0 if entity_type == "exempt_dealer" else VAT_RATE_BP


def split_vat(total: int, rate_bp: int) -> tuple[int, int]:
    """(net, vat) of a VAT-inclusive total in minor units; the two always add up to the total."""
    net = round(total * 10_000 / (10_000 + rate_bp))
    return net, total - net


def line_total(quantity: float, unit_price: int) -> int:
    return round(quantity * unit_price)


def needs_allocation(kind: str, net: int, currency: str) -> bool:
    return (
        kind in ("tax_invoice", "tax_invoice_receipt")
        and currency == "ILS"
        and (net > ALLOCATION_THRESHOLD)
    )
