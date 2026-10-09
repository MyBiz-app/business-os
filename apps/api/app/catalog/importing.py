"""Reading a client list from a CSV or Excel file: the file, its columns, and clean rows.

Businesses usually export from another system or keep a spreadsheet, often with Hebrew
headers and Windows encodings. This module only parses and validates; the API decides
what to insert."""

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

from email_validator import EmailNotValidError, validate_email
from openpyxl import load_workbook

ImportField = Literal[
    "first_name", "last_name", "full_name", "email", "phone", "date_of_birth", "notes", "status"
]

MAX_ROWS = 5000
MAX_BYTES = 2 * 1024 * 1024


class ImportFileError(Exception):
    """The file cannot be read as a table; `code` goes to the client."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _key(header: str) -> str:
    return re.sub(r"[\s_\-.\"'״׳:]+", "", header.strip().lower())


# Header text (normalized by _key) -> field. Hebrew and English, common export variants.
SYNONYMS: dict[str, ImportField] = {
    _key(name): target
    for target, names in {
        "first_name": ("first name", "firstname", "given name", "שם פרטי", "פרטי"),
        "last_name": ("last name", "lastname", "surname", "family name", "שם משפחה", "משפחה"),
        "full_name": ("name", "full name", "client", "member", "שם", "שם מלא", "לקוח", "מתאמן"),
        "email": ("email", "e-mail", "mail", "email address", "אימייל", "דוא\"ל", "דואל",
                  "מייל", "דואר אלקטרוני"),
        "phone": ("phone", "mobile", "cell", "phone number", "telephone", "טלפון", "נייד",
                  "סלולרי", "פלאפון", "מספר טלפון"),
        "date_of_birth": ("date of birth", "birthday", "birth date", "dob", "תאריך לידה",
                          "יום הולדת"),
        "notes": ("notes", "note", "comments", "remarks", "הערות", "הערה"),
        "status": ("status", "סטטוס", "מצב"),
    }.items()
    for name in names
}  # fmt: skip

STATUSES = {
    _key(word): value
    for value, words in {
        "active": ("active", "פעיל", "פעילה", "פעיל/ה", "כן", "yes"),
        "inactive": ("inactive", "לא פעיל", "לא פעילה", "לא פעיל/ה", "עזב", "עזבה", "no"),
        "lead": ("lead", "prospect", "ליד", "מתעניין", "מתעניינת", "מתעניין/ת"),
    }.items()
    for word in words
}

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%y", "%d.%m.%y")


def _decode(data: bytes) -> str:
    # Excel's "CSV UTF-8" adds a BOM; older Hebrew exports are Windows-1255.
    for encoding in ("utf-8-sig", "cp1255"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportFileError("unreadable_file")


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def read_table(data: bytes, filename: str) -> list[list[str]]:
    """The file as rows of text cells; the first row is the header. Empty rows are dropped."""
    if len(data) > MAX_BYTES:
        raise ImportFileError("file_too_large")
    if filename.lower().endswith((".xlsx", ".xlsm")) or data[:2] == b"PK":
        try:
            sheet = load_workbook(io.BytesIO(data), read_only=True, data_only=True).worksheets[0]
            rows = [[_cell(value) for value in row] for row in sheet.iter_rows(values_only=True)]
        except Exception as error:  # openpyxl raises many types for broken files
            raise ImportFileError("unreadable_file") from error
    else:
        content = _decode(data)
        try:
            dialect = csv.Sniffer().sniff(content[:4096], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = [[cell.strip() for cell in row] for row in csv.reader(io.StringIO(content), dialect)]
    rows = [row for row in rows if any(row)]
    if len(rows) < 2:
        raise ImportFileError("empty_file")
    if len(rows) - 1 > MAX_ROWS:
        raise ImportFileError("too_many_rows")
    width = max(len(row) for row in rows)
    return [row + [""] * (width - len(row)) for row in rows]


def suggest_mapping(headers: list[str]) -> list[ImportField | None]:
    """A field for each column whose header we recognize; each field is used at most once."""
    used: set[str] = set()
    mapping: list[ImportField | None] = []
    for header in headers:
        target = SYNONYMS.get(_key(header))
        if target in used:
            target = None
        if target:
            used.add(target)
        mapping.append(target)
    if "first_name" in used and "full_name" in used:  # "name" next to "first name"
        mapping = [None if target == "full_name" else target for target in mapping]
    return mapping


def phone_key(phone: str) -> str:
    """Digits only, Israeli +972 written as 0, for spotting the same number written twice."""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("972"):
        digits = "0" + digits[3:]
    return digits


def _phone(value: str) -> str:
    # Excel stores 0501234567 as the number 501234567.
    if re.fullmatch(r"5\d{8}", value):
        return "0" + value
    return value


def _date(value: str) -> date | None:
    for pattern in DATE_FORMATS:
        try:
            parsed = datetime.strptime(value, pattern).date()
        except ValueError:
            continue
        if parsed.year < 100:
            parsed = parsed.replace(year=parsed.year + (1900 if parsed.year > 30 else 2000))
        return parsed
    return None


@dataclass
class ParsedRow:
    line: int  # row number as the user sees it in the spreadsheet (header is 1)
    values: dict[str, object] = field(default_factory=dict)
    errors: list[tuple[str, str]] = field(default_factory=list)  # (field, code)


def parse_rows(table: list[list[str]], mapping: list[ImportField | None]) -> list[ParsedRow]:
    parsed: list[ParsedRow] = []
    for offset, row in enumerate(table[1:]):
        raw = {target: row[i] for i, target in enumerate(mapping) if target and row[i]}
        result = ParsedRow(line=offset + 2)
        values = result.values
        first = raw.get("first_name", "")
        last = raw.get("last_name", "")
        if not first and raw.get("full_name"):
            first, _, rest = raw["full_name"].partition(" ")
            last = last or rest.strip()
        if not first.strip():
            result.errors.append(("first_name", "missing_name"))
        values["first_name"] = first.strip()[:100]
        values["last_name"] = last.strip()[:100] or None
        email = raw.get("email")
        values["email"] = None
        if email:
            try:
                values["email"] = validate_email(email, check_deliverability=False).normalized
            except EmailNotValidError:
                result.errors.append(("email", "invalid_email"))
        values["phone"] = _phone(raw["phone"])[:30] if raw.get("phone") else None
        values["date_of_birth"] = None
        if raw.get("date_of_birth"):
            born = _date(raw["date_of_birth"])
            if born is None or not date(1900, 1, 1) <= born <= date.today():
                result.errors.append(("date_of_birth", "invalid_date"))
            values["date_of_birth"] = born
        values["notes"] = raw.get("notes", "")[:5000] or None
        values["status"] = "active"
        if raw.get("status"):
            mapped = STATUSES.get(_key(raw["status"]))
            if mapped is None:
                result.errors.append(("status", "invalid_status"))
            values["status"] = mapped or "active"
        parsed.append(result)
    return parsed
