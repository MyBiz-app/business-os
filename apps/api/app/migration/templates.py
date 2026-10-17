"""Saved column maps for systems whose export format is known. A file whose headers contain a
template's marker columns is read with the template, before any guessing. Add a system by adding
a `Template`: its marker headers and which header is which field."""

from dataclasses import dataclass

from app.catalog.importing import _key
from app.migration.fields import Kind


@dataclass(frozen=True)
class Template:
    id: str
    kind: Kind
    markers: tuple[str, ...]  # all of these headers must be present
    columns: dict[str, str]  # header -> field


TEMPLATES: tuple[Template, ...] = (
    Template(
        "google_contacts",
        "clients",
        ("First Name", "Last Name", "E-mail 1 - Value", "Phone 1 - Value"),
        {
            "First Name": "first_name",
            "Last Name": "last_name",
            "E-mail 1 - Value": "email",
            "Phone 1 - Value": "phone",
            "Birthday": "date_of_birth",
            "Notes": "notes",
        },
    ),
    Template(
        "outlook_contacts",
        "clients",
        ("First Name", "Last Name", "E-mail Address"),
        {
            "First Name": "first_name",
            "Last Name": "last_name",
            "E-mail Address": "email",
            "Mobile Phone": "phone",
            "Birthday": "date_of_birth",
            "Notes": "notes",
        },
    ),
)


def match_template(headers: list[str]) -> tuple[Template, list[str | None]] | None:
    """The first template this file matches, and the field of each column under it."""
    keys = {_key(header) for header in headers}
    for template in TEMPLATES:
        if all(_key(marker) in keys for marker in template.markers):
            table = {_key(name): field for name, field in template.columns.items()}
            used: set[str] = set()
            mapping: list[str | None] = []
            for header in headers:
                field = table.get(_key(header))
                if field in used:
                    field = None
                if field:
                    used.add(field)
                mapping.append(field)
            return template, mapping
    return None
