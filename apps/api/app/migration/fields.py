"""What a migration file can hold: the kinds of table, their fields, how headers map to fields
(first by name, in Hebrew and English) and how a row is read into clean values.

Clients reuse the client importer's parser. This module only reads and validates; `mover.py`
decides what to create."""

import re
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from typing import Literal

from email_validator import EmailNotValidError, validate_email

from app.catalog.importing import (
    SYNONYMS as CLIENT_SYNONYMS,
)
from app.catalog.importing import (
    ParsedRow,
    _date,
    _key,
    _phone,
    parse_rows,
)
from app.catalog.importing import suggest_mapping as suggest_client_mapping

Kind = Literal["clients", "memberships", "services", "staff", "appointments"]
KINDS: tuple[Kind, ...] = ("clients", "memberships", "services", "staff", "appointments")

ROLES = {
    _key(word): role
    for role, words in {
        "staff": ("staff", "instructor", "trainer", "coach", "מדריך", "מדריכה", "עובד", "עובדת"),
        "front_desk": ("front desk", "reception", "receptionist", "קבלה", "פקיד", "פקידה"),
        "manager": ("manager", "מנהל", "מנהלת"),
    }.items()
    for word in words
}


def _synonyms(table: dict[str, tuple[str, ...]]) -> dict[str, str]:
    return {_key(name): target for target, names in table.items() for name in names}


_PERSON = {
    "client_name": (
        "name",
        "full name",
        "client",
        "member",
        "customer",
        "שם",
        "שם מלא",
        "לקוח",
        "לקוחה",
        "מתאמן",
        "שם לקוח",
    ),
    "client_email": ("email", "e-mail", "mail", "client email", "אימייל", 'דוא"ל', "דואל", "מייל"),
    "client_phone": ("phone", "mobile", "cell", "telephone", "טלפון", "נייד", "סלולרי", "פלאפון"),
}

OTHER_SYNONYMS: dict[str, dict[str, str]] = {
    "memberships": _synonyms(
        {
            **_PERSON,
            "plan_name": (
                "plan",
                "membership",
                "package",
                "subscription",
                "card",
                "type",
                "מנוי",
                "כרטיסייה",
                "כרטיסיה",
                "חבילה",
                "סוג מנוי",
                "סוג",
            ),
            "credits_left": (
                "remaining",
                "balance",
                "credits left",
                "sessions left",
                "entries left",
                "left",
                "יתרה",
                "נותרו",
                "נשארו",
                "כניסות שנותרו",
                "כניסות נותרות",
                "כניסות שנשארו",
            ),
            "starts_on": (
                "start",
                "start date",
                "from",
                "begins",
                "תאריך התחלה",
                "התחלה",
                "מתאריך",
            ),
            "ends_on": (
                "end",
                "end date",
                "expires",
                "expiry",
                "valid until",
                "until",
                "תוקף",
                "תאריך סיום",
                "בתוקף עד",
                "תוקף עד",
                "סיום",
                "עד תאריך",
            ),
            "price": ("price", "amount", "paid", "מחיר", "סכום", "שולם"),
        }
    ),
    "services": _synonyms(
        {
            "name": (
                "name",
                "service",
                "service name",
                "class",
                "שם",
                "שירות",
                "שם שירות",
                "שיעור",
                "שם שיעור",
            ),
            "description": ("description", "details", "תיאור", "פרטים"),
            "duration_minutes": (
                "duration",
                "minutes",
                "length",
                "משך",
                "משך זמן",
                "דקות",
                "משך בדקות",
            ),
            "capacity": (
                "capacity",
                "max",
                "max participants",
                "places",
                "קיבולת",
                "מקומות",
                "מקסימום משתתפים",
                "מספר משתתפים",
            ),
            "price": ("price", "cost", "מחיר", "עלות"),
        }
    ),
    "staff": _synonyms(
        {
            "full_name": (
                "name",
                "full name",
                "employee",
                "staff",
                "instructor",
                "שם",
                "שם מלא",
                "עובד",
                "עובדת",
                "מדריך",
                "מדריכה",
            ),
            "email": ("email", "e-mail", "mail", "אימייל", 'דוא"ל', "דואל", "מייל"),
            "role": ("role", "position", "job title", "title", "תפקיד", "הרשאה"),
        }
    ),
    "appointments": _synonyms(
        {
            **_PERSON,
            "service_name": (
                "service",
                "treatment",
                "class",
                "appointment type",
                "שירות",
                "טיפול",
                "סוג טיפול",
                "שיעור",
                "סוג תור",
            ),
            "starts_at": (
                "start",
                "datetime",
                "date and time",
                "when",
                "תאריך ושעה",
                "מועד",
                "מתי",
            ),
            "date": ("date", "day", "תאריך", "יום"),
            "time": ("time", "start time", "hour", "שעה", "שעת התחלה", "בשעה"),
            "duration_minutes": ("duration", "minutes", "length", "משך", "דקות"),
        }
    ),
}

FIELDS: dict[str, tuple[str, ...]] = {
    "clients": tuple(dict.fromkeys(CLIENT_SYNONYMS.values())),
    **{kind: tuple(dict.fromkeys(table.values())) for kind, table in OTHER_SYNONYMS.items()},
}

# A file is taken for a kind when it has these (any one of each tuple).
ANCHORS: dict[str, tuple[tuple[str, ...], ...]] = {
    "appointments": (("service_name",), ("starts_at", "date")),
    "memberships": (("plan_name",), ("client_name", "client_email", "client_phone")),
    "staff": (("role",), ("email",)),
    "services": (("duration_minutes", "price", "capacity"), ("name",)),
    "clients": (("first_name", "last_name", "full_name"),),
}


def suggest_mapping(kind: str, headers: list[str]) -> list[str | None]:
    """A field for each column whose header we recognize; each field is used at most once."""
    if kind == "clients":
        return list(suggest_client_mapping(headers))
    table = OTHER_SYNONYMS[kind]
    used: set[str] = set()
    mapping: list[str | None] = []
    for header in headers:
        target = table.get(_key(header))
        if target in used:
            target = None
        if target:
            used.add(target)
        mapping.append(target)
    return mapping


def guess_kind(headers: list[str]) -> Kind | None:
    """What a file most likely holds, from its headers alone; None when nothing fits."""
    for kind in ("appointments", "memberships", "staff", "services", "clients"):
        fields = {f for f in suggest_mapping(kind, headers) if f}
        if all(fields.intersection(group) for group in ANCHORS[kind]):
            return kind  # type: ignore[return-value]
    return None


def valid_mapping(kind: str, headers: list[str], mapping: list[str | None]) -> bool:
    targets = [target for target in mapping if target]
    return (
        len(mapping) == len(headers)
        and len(targets) == len(set(targets))
        and set(targets) <= set(FIELDS[kind])
    )


def _email(value: str | None, result: ParsedRow, name: str) -> str | None:
    if not value:
        return None
    try:
        return validate_email(value, check_deliverability=False).normalized
    except EmailNotValidError:
        result.errors.append((name, "invalid_email"))
        return None


def _whole(value: str) -> int | None:
    cleaned = re.sub(r"[,\s]", "", value)
    try:
        number = Decimal(cleaned)
    except InvalidOperation:
        return None
    return int(number) if number == number.to_integral_value() else None


def _minor(value: str) -> int | None:
    """A price written in major units ("120", "₪1,200.50") as minor units (cents)."""
    cleaned = re.sub(r"[₪$€,\sA-Za-z]", "", value)
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return None
    if amount < 0 or amount > Decimal("10000000"):
        return None
    return int(amount * 100)


def _clock(value: str) -> time | None:
    match = re.fullmatch(r"(\d{1,2})[:.](\d{2})(?:[:.]\d{2})?", value.strip())
    if not match:
        return None
    hour, minute = int(match[1]), int(match[2])
    return time(hour, minute) if hour < 24 and minute < 60 else None


def _moment(value: str) -> datetime | None:
    """ "2026-11-03 17:30", "03/11/2026 17:30", or a bare date (midnight)."""
    parts = value.strip().split()
    day = _date(parts[0]) if parts else None
    if day is None:
        return None
    clock = _clock(parts[1]) if len(parts) > 1 else time(0, 0)
    return datetime.combine(day, clock) if clock else None


def _person(raw: dict[str, str], result: ParsedRow) -> dict[str, str | None]:
    person = {
        "name": raw.get("client_name") or None,
        "email": _email(raw.get("client_email"), result, "client_email"),
        "phone": _phone(raw["client_phone"])[:30] if raw.get("client_phone") else None,
    }
    if not any(person.values()) and not result.errors:
        result.errors.append(("client_name", "missing_client"))
    return person


def parse_other(kind: str, table: list[list[str]], mapping: list[str | None]) -> list[ParsedRow]:
    parsed: list[ParsedRow] = []
    for offset, row in enumerate(table[1:]):
        raw = {target: row[i] for i, target in enumerate(mapping) if target and row[i]}
        result = ParsedRow(line=offset + 2)
        values = result.values
        if kind == "memberships":
            values["client"] = _person(raw, result)
            values["plan_name"] = raw.get("plan_name", "").strip()[:120]
            if not values["plan_name"]:
                result.errors.append(("plan_name", "missing_plan"))
            values["credits"] = None
            if raw.get("credits_left"):
                credits = _whole(raw["credits_left"])
                if credits is None or credits < 0:
                    result.errors.append(("credits_left", "invalid_number"))
                values["credits"] = credits
            for name in ("starts_on", "ends_on"):
                values[name] = None
                if raw.get(name):
                    parsed_date = _date(raw[name])
                    if parsed_date is None:
                        result.errors.append((name, "invalid_date"))
                    values[name] = parsed_date
            if values["ends_on"] is None and not any(f == "ends_on" for f, _ in result.errors):
                result.errors.append(("ends_on", "invalid_date"))
            values["price_amount"] = 0
            if raw.get("price"):
                price = _minor(raw["price"])
                if price is None:
                    result.errors.append(("price", "invalid_price"))
                values["price_amount"] = price or 0
        elif kind == "services":
            values["name"] = raw.get("name", "").strip()[:120]
            if not values["name"]:
                result.errors.append(("name", "missing_name"))
            values["description"] = raw.get("description", "")[:2000] or None
            values["duration_minutes"] = 60
            if raw.get("duration_minutes"):
                minutes = _whole(raw["duration_minutes"])
                if minutes is None or not 5 <= minutes <= 1440:
                    result.errors.append(("duration_minutes", "invalid_number"))
                values["duration_minutes"] = minutes or 60
            values["capacity"] = 1
            if raw.get("capacity"):
                capacity = _whole(raw["capacity"])
                if capacity is None or not 1 <= capacity <= 1000:
                    result.errors.append(("capacity", "invalid_number"))
                values["capacity"] = capacity or 1
            values["price_amount"] = 0
            if raw.get("price"):
                price = _minor(raw["price"])
                if price is None:
                    result.errors.append(("price", "invalid_price"))
                values["price_amount"] = price or 0
        elif kind == "staff":
            values["full_name"] = raw.get("full_name", "").strip()[:200] or None
            values["email"] = _email(raw.get("email"), result, "email")
            if not raw.get("email"):
                result.errors.append(("email", "invalid_email"))
            values["role"] = "staff"
            if raw.get("role"):
                role = ROLES.get(_key(raw["role"]))
                if role is None:
                    result.errors.append(("role", "invalid_role"))
                values["role"] = role or "staff"
        else:  # appointments
            values["client"] = _person(raw, result)
            values["service_name"] = raw.get("service_name", "").strip()[:120]
            if not values["service_name"]:
                result.errors.append(("service_name", "missing_service"))
            moment = None
            if raw.get("starts_at"):
                moment = _moment(raw["starts_at"])
            elif raw.get("date"):
                day = _date(raw["date"].split()[0])
                clock = _clock(raw["time"]) if raw.get("time") else None
                if raw.get("date") and len(raw["date"].split()) > 1:
                    moment = _moment(raw["date"])
                elif day is not None and clock is not None:
                    moment = datetime.combine(day, clock)
            if moment is None:
                result.errors.append(("starts_at", "invalid_date"))
            values["starts_at"] = moment
            values["duration_minutes"] = None
            if raw.get("duration_minutes"):
                minutes = _whole(raw["duration_minutes"])
                if minutes is None or not 5 <= minutes <= 1440:
                    result.errors.append(("duration_minutes", "invalid_number"))
                values["duration_minutes"] = minutes
        parsed.append(result)
    return parsed


def parse(kind: str, table: list[list[str]], mapping: list[str | None]) -> list[ParsedRow]:
    if kind == "clients":
        return parse_rows(table, mapping)  # type: ignore[arg-type]
    return parse_other(kind, table, mapping)
