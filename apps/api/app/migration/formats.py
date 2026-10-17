"""Contact and calendar files as tables: a vCard (.vcf) or iCalendar (.ics) export becomes the
same header row plus rows that a spreadsheet would, so the rest of the move treats them alike."""

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.catalog.importing import MAX_ROWS, ImportFileError, read_table

VCARD_HEADERS = ["First name", "Last name", "Phone", "Email", "Notes"]
CALENDAR_HEADERS = ["Service", "Client", "Date", "Time", "Duration", "Location"]


def _unfold(text: str) -> list[str]:
    """Content lines with the folded continuations (a line starting with a space) joined."""
    lines: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line[:1] in (" ", "\t") and lines:
            lines[-1] += line[1:]
        elif line:
            lines.append(line)
    return lines


def _split(line: str) -> tuple[str, dict[str, str], str]:
    """(NAME, {PARAM: value}, value) of a content line such as `DTSTART;TZID=X:2026...`."""
    head, _, value = line.partition(":")
    name, *params = head.split(";")
    pairs = dict(p.split("=", 1) for p in params if "=" in p)
    return name.upper(), {k.upper(): v for k, v in pairs.items()}, value


def _unescape(value: str) -> str:
    return re.sub(r"\\([nN,;\\])", lambda m: "\n" if m[1] in "nN" else m[1], value).strip()


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1255"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportFileError("unreadable_file")


def is_contacts(data: bytes, filename: str) -> bool:
    return filename.lower().endswith(".vcf") or data.lstrip()[:11].upper() == b"BEGIN:VCARD"


def is_calendar(data: bytes, filename: str) -> bool:
    return filename.lower().endswith(".ics") or data.lstrip()[:15].upper() == b"BEGIN:VCALENDAR"


def read_contacts(data: bytes) -> list[list[str]]:
    rows: list[list[str]] = []
    card: dict[str, str] | None = None
    for line in _unfold(_decode(data)):
        name, _, value = _split(line)
        if name == "BEGIN" and value.upper() == "VCARD":
            card = {}
        elif name == "END" and value.upper() == "VCARD" and card is not None:
            if not card.get("first") and not card.get("last") and card.get("fn"):
                first, _, last = card["fn"].partition(" ")
                card["first"], card["last"] = first, last
            if any(card.values()):
                rows.append([card.get(k, "") for k in ("first", "last", "phone", "email", "notes")])
            card = None
        elif card is not None and value:
            if name == "N":
                parts = value.split(";")
                card["last"] = _unescape(parts[0])
                card["first"] = _unescape(parts[1]) if len(parts) > 1 else ""
            elif name == "FN":
                card["fn"] = _unescape(value)
            elif name in ("TEL", "EMAIL", "NOTE"):
                key = {"TEL": "phone", "EMAIL": "email", "NOTE": "notes"}[name]
                card.setdefault(key, _unescape(value))  # the first one listed
    return _table(VCARD_HEADERS, rows)


def _when(value: str, zone: ZoneInfo) -> datetime | None:
    """A DTSTART / DTEND value as a naive local time (UTC values move to the business zone)."""
    value = value.strip()
    try:
        if len(value) == 8:
            return datetime.strptime(value, "%Y%m%d")
        if value.endswith("Z"):
            moment = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
            return moment.astimezone(zone).replace(tzinfo=None)
        return datetime.strptime(value, "%Y%m%dT%H%M%S")
    except ValueError:
        return None


def read_calendar(data: bytes, time_zone: str) -> list[list[str]]:
    zone = ZoneInfo(time_zone)
    rows: list[list[str]] = []
    event: dict | None = None
    for line in _unfold(_decode(data)):
        name, params, value = _split(line)
        if name == "BEGIN" and value.upper() == "VEVENT":
            event = {}
        elif name == "END" and value.upper() == "VEVENT" and event is not None:
            start = event.get("start")
            if start is not None:
                end = event.get("end")
                minutes = int((end - start).total_seconds() // 60) if end else 0
                all_day = event.get("all_day", False)
                rows.append(
                    [
                        event.get("summary", ""),
                        event.get("client", ""),
                        start.strftime("%Y-%m-%d"),
                        "" if all_day else start.strftime("%H:%M"),
                        str(minutes) if minutes > 0 and not all_day else "",
                        event.get("location", ""),
                    ]
                )
            event = None
        elif event is not None:
            if name == "SUMMARY":
                event["summary"] = _unescape(value)[:120]
            elif name == "LOCATION":
                event["location"] = _unescape(value)[:120]
            elif name == "ATTENDEE" and "client" not in event and params.get("CN"):
                event["client"] = params["CN"].strip('"')
            elif name in ("DTSTART", "DTEND"):
                moment = _when(value, zone)
                if moment is not None:
                    event["start" if name == "DTSTART" else "end"] = moment
                    if name == "DTSTART":
                        event["all_day"] = params.get("VALUE") == "DATE" or len(value.strip()) == 8
    return _table(CALENDAR_HEADERS, rows)


def _table(headers: list[str], rows: list[list[str]]) -> list[list[str]]:
    if not rows:
        raise ImportFileError("empty_file")
    if len(rows) > MAX_ROWS:
        raise ImportFileError("too_many_rows")
    return [headers, *rows]


def read_any(data: bytes, filename: str, max_bytes: int, time_zone: str) -> list[list[str]]:
    """A spreadsheet, CSV, vCard or iCalendar file as rows of text; the first row is the header."""
    if len(data) > max_bytes:
        raise ImportFileError("file_too_large")
    if is_contacts(data, filename):
        return read_contacts(data)
    if is_calendar(data, filename):
        return read_calendar(data, time_zone)
    return read_table(data, filename, max_bytes)
