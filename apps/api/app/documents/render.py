"""The PDF engine: one Jinja template per document kind inside a shared brand frame
(`_frame.html`), turned into a PDF by WeasyPrint.

Hebrew and English both render right-to-left / left-to-right from the document's language
(`dir` on the page). The fonts (Assistant for Hebrew and text, Plus Jakarta Sans for English
headings) are bundled in `fonts/` so output does not depend on what the server has installed."""

import base64
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.documents import brand
from app.messaging.email import load_all_messages

HERE = Path(__file__).parent
DEFAULT_COLOR = "#2563EB"

_env = Environment(
    loader=FileSystemLoader(HERE / "templates"),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def language(locale: str | None) -> str:
    return "he" if locale == "he" else "en"


def texts(lang: str) -> dict[str, Any]:
    return load_all_messages(lang)["pdfDocuments"]


def fill(template: str, **values: object) -> str:
    for key, value in values.items():
        template = template.replace("{" + key + "}", str(value))
    return template


def money(amount: int, currency: str, lang: str) -> str:
    """Minor units as text: "₪1,250.00" in English, "1,250.00 ₪" in Hebrew."""
    digits = 0 if currency in ("JPY", "KRW", "VND") else 2
    number = f"{amount / 10**digits:,.{digits}f}"
    symbol = {"ILS": "₪", "USD": "$", "EUR": "€", "GBP": "£"}.get(currency, currency)
    separator = "" if symbol in ("₪", "$", "€", "£") else " "
    return f"{number}{separator}{symbol}" if lang == "he" else f"{symbol}{separator}{number}"


def day(value: date | datetime, lang: str, time_zone: str = "UTC") -> str:
    if isinstance(value, datetime):
        value = value.astimezone(ZoneInfo(time_zone)).date()
    return value.strftime("%d/%m/%Y") if lang == "he" else value.strftime("%b %d, %Y")


def data_uri(content: bytes, content_type: str) -> str:
    return f"data:{content_type};base64,{base64.b64encode(content).decode()}"


def mark_uri() -> str:
    return data_uri((HERE / "mark.svg").read_bytes(), "image/svg+xml")


def accent(color: str | None) -> str:
    """The business's brand color when it is a valid #rrggbb, else MyBiz blue."""
    if color and len(color) == 7 and color.startswith("#"):
        try:
            int(color[1:], 16)
        except ValueError:
            return DEFAULT_COLOR
        return color
    return DEFAULT_COLOR


def render_pdf(kind: str, lang: str, context: dict[str, Any]) -> bytes:
    """`kind` names a template ("receipt", "platform_invoice"); `context` is its data."""
    # Imported here: WeasyPrint loads Pango and about 60 MB, which only PDF requests need.
    from weasyprint import HTML

    html = _env.get_template(f"{kind}.html").render(
        lang=lang,
        dir="rtl" if lang == "he" else "ltr",
        t=texts(lang),
        brand_name=brand.NAME,
        mark=mark_uri(),
        issued_with=fill(texts(lang)["issuedWith"], brand=brand.NAME),
        **context,
    )
    return HTML(string=html, base_url=str(HERE)).write_pdf()
