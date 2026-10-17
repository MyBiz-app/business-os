"""Documents as PDF files, rendered on the server in the brand frame (app/documents/render.py):
a payment receipt (from the business to its client) and a MyBiz invoice (from MyBiz to the
business). The page's "print" button stays for a quick print; this is the file to keep or send."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.billing import Invoice, SettingsDep, _invoice
from app.api.common import not_found
from app.api.deps import ClientDep, TenantContext, require
from app.api.receipts import Receipt, _one
from app.core.config import get_settings
from app.core.permissions import Permission
from app.documents import brand, render
from app.messaging.email import load_all_messages

router = APIRouter(prefix="/documents/render", tags=["documents"])
client_router = APIRouter(prefix="/client", tags=["client"])

ReadDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_READ))]
PDF_RESPONSES: dict[int | str, dict[str, Any]] = {200: {"content": {"application/pdf": {}}}}


def _pdf(content: bytes, name: str) -> Response:
    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{name}.pdf"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _watermark(lang: str) -> str | None:
    return render.texts(lang)["stagingMark"] if get_settings().environment == "staging" else None


def _tenant(db: Session) -> dict[str, Any]:
    row = (
        db.execute(
            text("""
                SELECT name, locale, time_zone, primary_color, logo, logo_content_type
                FROM app.tenants
                WHERE id = coalesce(app.current_tenant_id(), app.client_tenant_id())
            """)
        )
        .mappings()
        .first()
    )
    if row is None:
        raise not_found()
    return dict(row)


def receipt_pdf(db: Session, receipt: Receipt) -> bytes:
    tenant = _tenant(db)
    lang = render.language(tenant["locale"])
    t = render.texts(lang)
    logo = (
        render.data_uri(bytes(tenant["logo"]), tenant["logo_content_type"])
        if tenant["logo"] and tenant["logo_content_type"]
        else None
    )
    return render.render_pdf(
        "receipt",
        lang,
        {
            "accent": render.accent(tenant["primary_color"]),
            "issuer": {"name": receipt.business_name, "logo": logo, "lines": []},
            "doc_title": t["receipt"],
            "doc_number": render.fill(t["receiptNumber"], number=receipt.number),
            "sample_note": t["sampleReceipt"] if receipt.simulated else None,
            "watermark": _watermark(lang),
            "footer_right": "",
            "issued": render.day(receipt.issued_at, lang, tenant["time_zone"]),
            "client_name": receipt.client_name,
            "client_email": receipt.client_email,
            "method": t["methods"][receipt.method],
            "description": receipt.description,
            "amount": render.money(receipt.amount, receipt.currency, lang),
        },
    )


def platform_invoice_pdf(db: Session, invoice: Invoice) -> bytes:
    tenant = _tenant(db)
    lang = render.language(tenant["locale"])
    t = render.texts(lang)
    names = load_module_names(lang)

    def money(amount: int) -> str:
        return render.money(amount, invoice.currency, lang)

    lines = [
        {
            "label": t["core"] if line.key == "core" else names.get(line.key, line.key),
            "quantity": line.quantity,
            "detail": (
                render.fill(t["activeClients"], count=invoice.active_clients)
                if line.key == "core"
                else None
            ),
            "amount": money(line.amount),
        }
        for line in invoice.lines
    ]
    paid = invoice.status == "paid" and invoice.paid_at is not None
    note = (
        render.fill(
            t["paidWith"],
            last4=invoice.card_last4 or "",
            date=render.day(invoice.paid_at, lang, tenant["time_zone"]),
        )
        if paid and invoice.paid_at
        else None
    )
    legal = {
        "name": brand.COMPANY_NAME[lang],
        "lines": [
            brand.ADDRESS[lang],
            f"{t['companyNumber']} {brand.COMPANY_NUMBER}",
            f"{t['vatNumber']} {brand.VAT_NUMBER}",
            brand.EMAIL,
            brand.WEBSITE,
        ],
        "logo": render.mark_uri(),
        "is_mark": True,
    }
    return render.render_pdf(
        "platform_invoice",
        lang,
        {
            "accent": render.DEFAULT_COLOR,
            "issuer": legal,
            "doc_title": t["invoice"],
            "doc_number": render.fill(t["invoiceNumber"], number=invoice.number),
            "sample_note": t["sampleInvoice"] if invoice.simulated else None,
            "watermark": _watermark(lang) or (t["stagingMark"] if brand.FICTITIOUS else None),
            "footer_right": "",
            "issued": render.day(invoice.issued_at, lang, tenant["time_zone"]),
            "period": " - ".join(
                render.day(d, lang) for d in (invoice.period_start, invoice.period_end)
            ),
            "client_name": invoice.billing.billing_name or invoice.business_name,
            "client_tax_id": invoice.billing.tax_id,
            "client_email": invoice.billing.billing_email,
            "lines": lines,
            "vat": (
                {
                    "subtotal_label": t["subtotal"],
                    "subtotal": money(invoice.subtotal),
                    "label": render.fill(t["vat"], rate=f"{invoice.vat_rate_bp / 100:g}"),
                    "amount": money(invoice.vat_amount),
                }
                if invoice.vat_rate_bp
                else None
            ),
            "total": money(invoice.total),
            "status_label": t["status"][invoice.status] if invoice.status != "open" else None,
            "paid": paid,
            "payment_note": note,
        },
    )


def load_module_names(lang: str) -> dict[str, str]:
    return load_all_messages(lang)["modules"]["names"]


@router.get("/receipt/{receipt_id}.pdf", response_class=Response, responses=PDF_RESPONSES)
def receipt_file(receipt_id: UUID, context: ReadDep) -> Response:
    receipt = _one(context.session, receipt_id)
    return _pdf(receipt_pdf(context.session, receipt), f"receipt-{receipt.number}")


@router.get("/platform_invoice/{invoice_id}.pdf", response_class=Response, responses=PDF_RESPONSES)
def platform_invoice_file(invoice_id: UUID, context: SettingsDep) -> Response:
    invoice = _invoice(context.session, invoice_id)
    return _pdf(platform_invoice_pdf(context.session, invoice), f"invoice-{invoice.number}")


@client_router.get("/receipts/{receipt_id}.pdf", response_class=Response, responses=PDF_RESPONSES)
def my_receipt_file(receipt_id: UUID, context: ClientDep) -> Response:
    receipt = _one(context.session, receipt_id)
    if receipt.client_id != context.client_id:
        raise not_found()
    return _pdf(receipt_pdf(context.session, receipt), f"receipt-{receipt.number}")
