"""Importing clients from a CSV or Excel file: preview first, then import.

Both steps upload the same file; the preview changes nothing. Rows that match an existing
client or an earlier row (same email, same phone number, or - with neither - the same full
name) are skipped, never merged."""

import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.api.clients import ClientSource
from app.api.deps import TenantContext, require
from app.catalog.importing import (
    MAX_BYTES,
    ImportField,
    ImportFileError,
    parse_rows,
    phone_key,
    read_table,
    suggest_mapping,
)
from app.core.permissions import Permission
from app.files.scan import ensure_clean
from app.geo.addresses import CityMatcher

router = APIRouter(prefix="/clients", tags=["clients"])

WriteDep = Annotated[TenantContext, Depends(require(Permission.CLIENTS_WRITE))]

MAX_ISSUES = 50
MAPPING = TypeAdapter(list[ImportField | None])


class ImportIssue(BaseModel):
    line: int = Field(description="Row number in the file (the header is row 1)")
    field: str | None
    code: Literal[
        "missing_name",
        "invalid_email",
        "invalid_date",
        "invalid_status",
        "duplicate",
        "unknown_city",
    ]


class ImportedClient(BaseModel):
    first_name: str
    last_name: str | None
    email: str | None
    phone: str | None
    city: str | None = Field(default=None, description="The official city it was matched to")


class ImportResult(BaseModel):
    columns: list[str] = Field(description="Header of each column in the file")
    mapping: list[ImportField | None] = Field(description="Field for each column, if any")
    examples: list[str] = Field(description="First non-empty value of each column")
    rows: int
    ready: int = Field(description="New clients the import adds (or added)")
    duplicates: int
    invalid: int
    cities_matched: int = Field(description="New clients whose city was found in the official list")
    cities_unmatched: int = Field(
        description="New clients whose city was not recognized; they are imported without a city"
    )
    imported: bool
    issues: list[ImportIssue] = Field(description=f"The first {MAX_ISSUES} problems")
    sample: list[ImportedClient] = Field(description="The first new clients")


def _name_key(first_name: str, last_name: str | None) -> str:
    return " ".join(f"{first_name} {last_name or ''}".lower().split())


def _bad_request(code: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=code)


@router.post("/import")
def import_clients(
    file: UploadFile,
    context: WriteDep,
    mapping: Annotated[
        str | None, Form(description="JSON list: a field (or null) per column")
    ] = None,
    commit: Annotated[bool, Form(description="false: preview only")] = False,
    source: Annotated[ClientSource | None, Form()] = None,
) -> ImportResult:
    data = file.file.read(MAX_BYTES + 1)
    ensure_clean(data)
    try:
        table = read_table(data, file.filename or "")
    except ImportFileError as error:
        raise _bad_request(error.code) from error
    headers = table[0]
    if mapping is None:
        columns = suggest_mapping(headers)
    else:
        try:
            columns = MAPPING.validate_python(json.loads(mapping))
        except (json.JSONDecodeError, ValidationError) as error:
            raise _bad_request("invalid_mapping") from error
        targets = [target for target in columns if target]
        if len(columns) != len(headers) or len(targets) != len(set(targets)):
            raise _bad_request("invalid_mapping")

    db = context.session
    existing = db.execute(
        text("SELECT lower(email), phone, first_name, last_name FROM app.clients")
    ).all()
    emails = {row[0] for row in existing if row[0]}
    phones = {phone_key(row[1]) for row in existing if row[1] and phone_key(row[1])}
    names = {_name_key(row[2], row[3]) for row in existing}

    cities = CityMatcher(db)
    city_names = {
        code: name for code, name in db.execute(text("SELECT code, name_he FROM app.geo_cities"))
    }
    issues: list[ImportIssue] = []
    ready: list[dict] = []
    duplicates = invalid = matched = unmatched = 0
    for row in parse_rows(table, columns):
        if row.errors:
            invalid += 1
            issues.extend(ImportIssue(line=row.line, field=f, code=c) for f, c in row.errors)
            continue
        email = row.values["email"]
        phone = phone_key(row.values["phone"] or "")
        name = _name_key(row.values["first_name"], row.values["last_name"])
        # Without an email or phone, the same full name is the only hint of a duplicate.
        if (
            (email and email.lower() in emails)
            or (phone and phone in phones)
            or (not email and not phone and name in names)
        ):
            duplicates += 1
            issues.append(ImportIssue(line=row.line, field=None, code="duplicate"))
            continue
        if email:
            emails.add(email.lower())
        if phone:
            phones.add(phone)
        names.add(name)
        city_code = cities.find(row.values["city"])
        if row.values["city"] and city_code is None:
            unmatched += 1
            # Not a reason to leave the client out: they come in without a city.
            issues.append(ImportIssue(line=row.line, field="city", code="unknown_city"))
        elif city_code is not None:
            matched += 1
        ready.append({**row.values, "city_code": city_code})

    if commit and ready:
        try:
            db.execute(
                text("""
                    INSERT INTO app.clients
                        (tenant_id, first_name, last_name, email, phone, date_of_birth, notes,
                         status, source, city_code)
                    VALUES (:tenant_id, :first_name, :last_name, :email, :phone, :date_of_birth,
                            :notes, :status, :source, :city_code)
                """),
                [
                    {
                        **{k: v for k, v in values.items() if k != "city"},
                        "tenant_id": context.tenant_id,
                        "source": source,
                    }
                    for values in ready
                ],
            )
        except IntegrityError as error:  # another import added the same email meanwhile
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="email_taken"
            ) from error
        db.execute(
            text("""
                INSERT INTO app.audit_log (tenant_id, actor_type, actor_id, action, details)
                VALUES (:tenant_id, 'user', app.current_user_id(), 'clients.import', :details)
            """),
            {
                "tenant_id": context.tenant_id,
                "details": json.dumps(
                    {
                        "file": file.filename,
                        "created": len(ready),
                        "duplicates": duplicates,
                        "invalid": invalid,
                    },
                    ensure_ascii=False,
                ),
            },
        )

    return ImportResult(
        columns=headers,
        mapping=columns,
        examples=[next((row[i] for row in table[1:] if row[i]), "") for i in range(len(headers))],
        rows=len(table) - 1,
        ready=len(ready),
        duplicates=duplicates,
        invalid=invalid,
        cities_matched=matched,
        cities_unmatched=unmatched,
        imported=commit and bool(ready),
        issues=issues[:MAX_ISSUES],
        sample=[
            ImportedClient.model_validate({**v, "city": city_names.get(v["city_code"])})
            for v in ready[:5]
        ],
    )
