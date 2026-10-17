"""What an uploaded file really is, from its bytes (GL3). The type the browser claims is only a
claim: a script renamed `.pdf` still says `application/pdf`. Every upload point checks the first
bytes against the type it accepts before anything is stored."""

import io
import zipfile

from fastapi import HTTPException, status

PNG = b"\x89PNG\r\n\x1a\n"
OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # the old Word and Excel container
ZIP = b"PK\x03\x04"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# Programs and archives are never text, however the file is named.
_BINARY_STARTS = (b"MZ", b"\x7fELF", b"\xca\xfe\xba\xbe", b"\xfe\xed\xfa", b"#!", PNG, OLE, ZIP)
_TEXT_TYPES = {"text/plain", "text/csv"}


def _is_text(data: bytes) -> bool:
    head = data[:8192]
    if head.startswith((b"\xff\xfe", b"\xfe\xff")):  # UTF-16 with a byte order mark
        return True
    if b"\x00" in head or head.startswith(_BINARY_STARTS) or head.startswith(b"%PDF-"):
        return False
    return not head.lstrip().lower().startswith((b"<script", b"<html", b"<!doctype html"))


def _office_zip(data: bytes, content_type: str) -> bool:
    """A real Word or Excel file: a zip with its part folder, not any archive."""
    folder = "word/" if content_type == DOCX else "xl/"
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile:
        return False
    return "[Content_Types].xml" in names and any(n.startswith(folder) for n in names)


def matches(data: bytes, content_type: str) -> bool:
    """Do the bytes fit the claimed type?"""
    if content_type == "application/pdf":
        return b"%PDF-" in data[:1024]  # the format allows a short lead-in
    if content_type == "image/png":
        return data.startswith(PNG)
    if content_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if content_type == "image/webp":
        return data.startswith(b"RIFF") and data[8:12] == b"WEBP"
    if content_type in ("application/msword", "application/vnd.ms-excel"):
        return data.startswith(OLE)
    if content_type in (DOCX, XLSX):
        return data.startswith(ZIP) and _office_zip(data, content_type)
    if content_type in _TEXT_TYPES:
        return _is_text(data)
    return False


def ensure_matches(data: bytes, content_type: str) -> None:
    """422 `unsupported_type` when the content is not what the type says."""
    if not matches(data, content_type):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="unsupported_type"
        )


def detect_import_type(data: bytes) -> str:
    """The stored type of a spreadsheet or contacts file the migration hub read: a real
    spreadsheet is recognised by its bytes, anything else it parsed is text."""
    if data.startswith(ZIP):
        return XLSX
    if data.startswith(OLE):
        return "application/vnd.ms-excel"
    return "text/plain"
