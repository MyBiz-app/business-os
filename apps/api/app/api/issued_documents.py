"""Documents a business issues to its clients, as stored PDFs with a running number per kind
(migration 0105, templates in app/documents/templates): tax invoice-receipt, tax invoice, credit
note, quote and transaction invoice. Receipts keep their own flow (receipts.py), payslips are
plain and not part of this.

An issued document is kept exactly as produced (with its sha256) and never edited: a mistake is
fixed with a credit note. The first file is the original; a later download can ask for a copy,
rendered again from the stored data. While the invoicing provider (#47) is disabled every
document is marked as a sample, and a tax invoice above the allocation threshold says its
allocation number is still to come."""

import hashlib
import json
from datetime import date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.common import not_found
from app.api.deps import TenantContext, require
from app.api.pagination import PageDep
from app.api.pdf import PDF_RESPONSES, _pdf, _watermark
from app.core.legal_readiness import evaluate
from app.core.permissions import Permission
from app.documents import issuing, render
from app.documents.issuing import FIRST_NUMBER, Kind

router = APIRouter(prefix="/issued-documents", tags=["documents"])

SalesDep = Annotated[TenantContext, Depends(require(Permission.SALES_MANAGE))]
PaymentMethod = Literal["card", "cash", "transfer", "other"]
KINDS: tuple[str, ...] = (
    "tax_invoice_receipt",
    "tax_invoice",
    "credit_note",
    "quote",
    "transaction_invoice",
)
TITLES = {
    "tax_invoice_receipt": "taxInvoiceReceipt",
    "tax_invoice": "taxInvoice",
    "credit_note": "creditNote",
    "quote": "quote",
    "transaction_invoice": "transactionInvoice",
}
# Credit notes use the soft red bar; every other kind uses the business's brand color.
CREDIT_RED = "#dc2626"


class LineIn(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    quantity: float = Field(default=1, gt=0, le=100_000)
    unit_price: int = Field(ge=0, le=1_000_000_000, description="Minor units, VAT included")


class IssueRequest(BaseModel):
    kind: Kind
    client_id: UUID | None = None
    client_name: str | None = Field(default=None, min_length=1, max_length=200)
    client_email: str | None = Field(default=None, max_length=200)
    client_tax_id: str | None = Field(default=None, max_length=20)
    lines: list[LineIn] = Field(min_length=1, max_length=50)
    payment_method: PaymentMethod | None = None
    due_date: date | None = None
    valid_until: date | None = None
    payment_terms: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=1000)
    reference_id: UUID | None = Field(default=None, description="The invoice a credit note credits")
    allocation_number: str | None = Field(
        default=None, max_length=40, description="From the tax authority, via the provider"
    )

    @model_validator(mode="after")
    def _kind_rules(self) -> "IssueRequest":
        credit = self.kind == "credit_note"
        if credit != (self.reference_id is not None):
            raise ValueError("reference_id is for credit notes, and credit notes need it")
        if not credit and not (self.client_id or self.client_name):
            raise ValueError("client_id or client_name is required")
        if self.kind == "tax_invoice_receipt" and self.payment_method is None:
            raise ValueError("payment_method is required for a tax invoice-receipt")
        return self


class IssuedLine(BaseModel):
    description: str
    quantity: float
    unit_price: int
    amount: int


class IssuedDocument(BaseModel):
    id: UUID
    kind: Kind
    number: int
    issued_at: datetime
    language: Literal["he", "en"]
    client_id: UUID | None
    client_name: str
    client_email: str | None
    client_tax_id: str | None
    currency: str
    lines: list[IssuedLine]
    vat_rate_bp: int
    net: int
    vat: int
    total: int = Field(description="Minor units, VAT included")
    payment_method: PaymentMethod | None
    due_date: date | None
    valid_until: date | None
    payment_terms: str | None
    notes: str | None
    reference_id: UUID | None
    allocation_required: bool
    allocation_number: str | None
    content_hash: str = Field(description="sha256 of the stored PDF")


class SeriesRow(BaseModel):
    kind: Kind
    next_number: int


COLUMNS = """
    id, kind, number, issued_at, language, client_id, client_name, client_email, client_tax_id,
    currency, lines, vat_rate_bp, net, vat, total, payment_method, due_date, valid_until,
    payment_terms, notes, reference_id, allocation_required, allocation_number, content_hash
"""


def _tenant(db: Session) -> dict[str, Any]:
    row = (
        db.execute(
            text("""
                SELECT name, locale, time_zone, primary_color, logo, logo_content_type, currency,
                       legal_entity_type, business_number, address_line, address_city,
                       employer_file_number, business_license_number,
                       business_license_expires_on,
                       (now() AT TIME ZONE time_zone)::date AS today
                FROM app.tenants WHERE id = app.current_tenant_id()
            """)
        )
        .mappings()
        .one()
    )
    return dict(row)


def _check_can_issue(kind: str, tenant: dict[str, Any]) -> None:
    """Exempt dealers get receipts and transaction invoices only; a tax document also needs the
    business's number and address (the readiness card shows what is missing)."""
    if kind not in issuing.TAX_KINDS:
        return
    if tenant["legal_entity_type"] == "exempt_dealer":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="exempt_dealer_no_tax_invoice")
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
    if not readiness.tax_invoice:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="legal_details_missing")


def _client(db: Session, client_id: UUID) -> dict[str, Any]:
    row = (
        db.execute(
            text("""
                SELECT id, trim(first_name || ' ' || coalesce(last_name, '')) AS name, email
                FROM app.clients WHERE id = :id AND erased_at IS NULL
            """),
            {"id": client_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="unknown_client")
    return dict(row)


def _credit_target(db: Session, reference_id: UUID, total: int) -> dict[str, Any]:
    """The invoice a credit note credits; the notes together may not exceed it."""
    # Two credit notes for one invoice at once must not both pass the check below.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:id))"), {"id": str(reference_id)})
    original = (
        db.execute(
            text("""
                SELECT id, kind, number, client_id, client_name, client_email, client_tax_id,
                       currency, total,
                       (SELECT coalesce(sum(c.total), 0) FROM app.issued_documents c
                        WHERE c.reference_id = d.id) AS credited
                FROM app.issued_documents d
                WHERE id = :id AND kind IN ('tax_invoice', 'tax_invoice_receipt')
            """),
            {"id": reference_id},
        )
        .mappings()
        .first()
    )
    if original is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="unknown_invoice")
    if total > original["total"] - original["credited"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="credit_exceeds_invoice")
    return dict(original)


def _logo(tenant: dict[str, Any]) -> str | None:
    if tenant["logo"] and tenant["logo_content_type"]:
        return render.data_uri(bytes(tenant["logo"]), tenant["logo_content_type"])
    return None


def document_pdf(
    tenant: dict[str, Any], doc: dict[str, Any], *, copy: bool, reference_number: int | None
) -> bytes:
    """The PDF of one document row (`doc` has the columns of the table). Pure rendering."""
    lang = doc["language"]
    t = render.texts(lang)
    kind = doc["kind"]
    currency = doc["currency"]
    tz = tenant["time_zone"]

    def money(amount: int) -> str:
        return render.money(amount, currency, lang)

    issuer_lines = [
        ", ".join(p for p in (tenant["address_line"], tenant["address_city"]) if p),
        f"{t['businessNumber']} {tenant['business_number']}" if tenant["business_number"] else "",
    ]
    show_vat = kind in issuing.VAT_KINDS
    rate = doc["vat_rate_bp"] / 100
    due = doc["due_date"]
    valid = doc["valid_until"]
    return render.render_pdf(
        kind,
        lang,
        {
            "accent": CREDIT_RED
            if kind == "credit_note"
            else render.accent(tenant["primary_color"]),
            "issuer": {
                "name": tenant["name"],
                "logo": _logo(tenant),
                "lines": [line for line in issuer_lines if line],
            },
            "doc_title": t[TITLES[kind]],
            "doc_number": render.fill(t["documentNumber"], number=doc["number"]),
            "version_label": t["copy"] if copy else t["original"],
            "sample_note": t["sampleIssued"],
            "watermark": _watermark(lang),
            "footer_right": "",
            "issued": render.day(doc["issued_at"], lang, tz),
            "client_name": doc["client_name"],
            "client_email": doc["client_email"],
            "client_tax_id": doc["client_tax_id"],
            "reference": (
                render.fill(t["creditFor"], number=reference_number) if reference_number else None
            ),
            "payment_method": t["methods"][doc["payment_method"]]
            if doc["payment_method"]
            else None,
            "lines": [
                {
                    "description": line["description"],
                    "quantity": f"{line['quantity']:g}",
                    "unit_price": money(line["unit_price"]),
                    "amount": money(line["amount"]),
                }
                for line in doc["lines"]
            ],
            "show_vat": show_vat,
            "net": money(doc["net"]),
            "vat": money(doc["vat"]),
            "vat_label": render.fill(t["vat"], rate=f"{rate:g}"),
            "total": money(doc["total"]),
            "due_text": render.fill(t["dueBy"], date=render.day(due, lang)) if due else None,
            "valid_text": render.fill(t["validUntil"], date=render.day(valid, lang))
            if valid
            else None,
            "payment_terms": doc["payment_terms"],
            "notes": doc["notes"],
            "allocation": doc["allocation_number"],
            "allocation_pending": doc["allocation_required"] and not doc["allocation_number"],
        },
    )


def _row(db: Session, document_id: UUID) -> dict[str, Any]:
    row = (
        db.execute(
            text(f"SELECT {COLUMNS} FROM app.issued_documents WHERE id = :id"),
            {"id": document_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return dict(row)


@router.post("", status_code=status.HTTP_201_CREATED)
def issue(body: IssueRequest, context: SalesDep) -> IssuedDocument:
    """Takes the next number of the kind, renders the PDF and stores both in one transaction."""
    db = context.session
    tenant = _tenant(db)
    _check_can_issue(body.kind, tenant)

    lines = [
        {
            "description": line.description,
            "quantity": line.quantity,
            "unit_price": line.unit_price,
            "amount": issuing.line_total(line.quantity, line.unit_price),
        }
        for line in body.lines
    ]
    total = sum(line["amount"] for line in lines)
    currency = tenant["currency"]
    reference: dict[str, Any] | None = None
    if body.kind == "credit_note" and body.reference_id:
        reference = _credit_target(db, body.reference_id, total)
        currency = reference["currency"]
        client = {
            "client_id": reference["client_id"],
            "client_name": reference["client_name"],
            "client_email": reference["client_email"],
            "client_tax_id": reference["client_tax_id"],
        }
    elif body.client_id:
        found = _client(db, body.client_id)
        client = {
            "client_id": found["id"],
            "client_name": body.client_name or found["name"],
            "client_email": body.client_email or found["email"],
            "client_tax_id": body.client_tax_id,
        }
    else:
        client = {
            "client_id": None,
            "client_name": body.client_name,
            "client_email": body.client_email,
            "client_tax_id": body.client_tax_id,
        }

    rate = issuing.vat_rate_bp(tenant["legal_entity_type"])
    net, vat = issuing.split_vat(total, rate)
    document_id = uuid4()
    number = db.execute(
        text("SELECT app.next_document_number(:kind)"), {"kind": body.kind}
    ).scalar_one()
    doc: dict[str, Any] = {
        "id": document_id,
        "kind": body.kind,
        "number": number,
        "issued_at": datetime.now().astimezone(),
        "language": render.language(tenant["locale"]),
        "currency": currency,
        "lines": lines,
        "vat_rate_bp": rate,
        "net": net,
        "vat": vat,
        "total": total,
        "payment_method": body.payment_method,
        "due_date": body.due_date,
        "valid_until": body.valid_until,
        "payment_terms": body.payment_terms,
        "notes": body.notes,
        "reference_id": body.reference_id,
        "allocation_required": issuing.needs_allocation(body.kind, net, currency),
        "allocation_number": body.allocation_number,
        **client,
    }
    content = document_pdf(
        tenant, doc, copy=False, reference_number=reference["number"] if reference else None
    )
    db.execute(
        text("""
            INSERT INTO app.issued_documents (
                id, tenant_id, kind, number, issued_at, language, client_id, client_name,
                client_email, client_tax_id, currency, lines, vat_rate_bp, net, vat, total,
                payment_method, due_date, valid_until, payment_terms, notes, reference_id,
                allocation_required, allocation_number, content, content_hash, issued_by)
            VALUES (
                :id, app.current_tenant_id(), :kind, :number, :issued_at, :language, :client_id,
                :client_name, :client_email, :client_tax_id, :currency,
                cast(:lines AS jsonb), :vat_rate_bp, :net, :vat, :total, :payment_method,
                :due_date, :valid_until, :payment_terms, :notes, :reference_id,
                :allocation_required, :allocation_number, :content, :content_hash,
                app.current_user_id())
        """),
        {
            **doc,
            "lines": json.dumps(lines),
            "content": content,
            "content_hash": hashlib.sha256(content).hexdigest(),
        },
    )
    return IssuedDocument.model_validate(_row(db, document_id))


@router.get("")
def list_issued(
    context: SalesDep,
    page: PageDep,
    kind: Annotated[Kind | None, Query()] = None,
    client_id: Annotated[UUID | None, Query()] = None,
) -> list[IssuedDocument]:
    """Newest first."""
    rows = context.session.execute(
        text(f"""
            SELECT {COLUMNS} FROM app.issued_documents
            WHERE (cast(:kind AS text) IS NULL OR kind = :kind)
              AND (cast(:client_id AS uuid) IS NULL OR client_id = :client_id)
            ORDER BY issued_at DESC, number DESC
            LIMIT :limit OFFSET :offset
        """),
        {"kind": kind, "client_id": client_id, "limit": page.limit, "offset": page.offset},
    ).mappings()
    return [IssuedDocument.model_validate(dict(row)) for row in rows]


@router.get("/series")
def series(context: SalesDep) -> list[SeriesRow]:
    """The number each kind will get next."""
    rows = context.session.execute(text("SELECT kind, last FROM app.document_series"))
    last = {row.kind: row.last for row in rows}
    return [
        SeriesRow(kind=kind, next_number=last[kind] + 1 if kind in last else FIRST_NUMBER)
        for kind in KINDS
    ]


@router.get("/{document_id}.pdf", response_class=Response, responses=PDF_RESPONSES)
def issued_file(
    document_id: UUID,
    context: SalesDep,
    copy: Annotated[bool, Query(description="A copy, rendered again from the stored data")] = False,
) -> Response:
    """The stored original, byte for byte; `copy=true` renders a copy marked as such."""
    db = context.session
    doc = _row(db, document_id)
    name = f"{doc['kind'].replace('_', '-')}-{doc['number']}"
    if not copy:
        content = db.execute(
            text("SELECT content FROM app.issued_documents WHERE id = :id"), {"id": document_id}
        ).scalar_one()
        return _pdf(bytes(content), name)
    reference_number = None
    if doc["reference_id"]:
        reference_number = db.execute(
            text("SELECT number FROM app.issued_documents WHERE id = :id"),
            {"id": doc["reference_id"]},
        ).scalar_one()
    return _pdf(
        document_pdf(_tenant(db), doc, copy=True, reference_number=reference_number),
        f"{name}-copy",
    )


@router.get("/{document_id}", response_model=IssuedDocument)
def get_issued(document_id: UUID, context: SalesDep) -> dict[str, Any]:
    return _row(context.session, document_id)
