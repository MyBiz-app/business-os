"""MyBiz's own company details, printed on documents MyBiz issues to a business.

The fictitious placeholder details live in packages/i18n/brand.json (`legal`); the API image is
built from apps/api alone, so this is the checked-in copy. A test fails when they differ.
Replacing them with the real company's details is one change to brand.json plus this file."""

from typing import Final

NAME: Final = "MyBiz"
COMPANY_NAME: Final = {"he": 'מייביז טכנולוגיות בע"מ', "en": "MyBiz Technologies Ltd."}
COMPANY_NUMBER: Final = "516000106"
VAT_NUMBER: Final = "516000106"
ADDRESS: Final = {
    "he": "רחוב הדוגמה 1, תל אביב-יפו 6100001",
    "en": "1 Hadugma St., Tel Aviv-Yafo 6100001",
}
EMAIL: Final = "billing@mybizapp.click"
WEBSITE: Final = "mybizapp.click"
FICTITIOUS: Final = True
