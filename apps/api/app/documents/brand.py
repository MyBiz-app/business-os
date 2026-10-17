"""The company's own details, printed on documents it issues to a business.

They come from `legal` in packages/i18n/brand.json (through the copy in app/core/brand.json, see
app/core/brand.py). The details there are fictitious placeholders until the real company's are
filled in: that is one change to brand.json, then `pnpm brand:sync`."""

from typing import Final

from app.core.brand import BRAND, NAME

LEGAL: Final = BRAND["legal"]

COMPANY_NAME: Final[dict[str, str]] = LEGAL["companyName"]
COMPANY_NUMBER: Final[str] = LEGAL["companyNumber"]
VAT_NUMBER: Final[str] = LEGAL["vatNumber"]
ADDRESS: Final[dict[str, str]] = LEGAL["address"]
EMAIL: Final[str] = LEGAL["email"]
WEBSITE: Final[str] = LEGAL["website"]
FICTITIOUS: Final[bool] = LEGAL["fictitious"]

__all__ = [
    "ADDRESS",
    "COMPANY_NAME",
    "COMPANY_NUMBER",
    "EMAIL",
    "FICTITIOUS",
    "NAME",
    "VAT_NUMBER",
    "WEBSITE",
]
