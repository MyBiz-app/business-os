"""Running a move: reads each file of a session, creates what it holds and records everything the
batch created, so it can be undone.

A dry run executes the very same code inside a savepoint and rolls it back, so the preview shows
exactly what the import would do, constraints included. Order matters: services and staff first,
then clients, then what hangs on clients (memberships with their balances, future appointments)."""

import hashlib
import json
import secrets
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.catalog.importing import ImportFileError, phone_key, read_table
from app.files import read_file
from app.migration.fields import KINDS, parse

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_MOVE_BYTES = 20 * 1024 * 1024
MAX_ISSUES = 50
UNDO_DAYS = 14
INVITATION_DAYS = 7


class MoveIssue(BaseModel):
    line: int = Field(description="Row number in the file (the header is row 1)")
    field: str | None
    code: str


class MoveFileReport(BaseModel):
    import_file_id: UUID
    filename: str
    kind: str | None
    rows: int
    ready: int = Field(description="New records the import creates (or created)")
    duplicates: int
    invalid: int
    skipped: int = Field(description="Rows left out on purpose (expired, past, empty balance)")
    issues: list[MoveIssue] = Field(description=f"The first {MAX_ISSUES} problems")
    sample: list[dict[str, str]] = Field(description="The first records to be created")


class MoveInvitation(BaseModel):
    email: str
    role: str
    token: str = Field(description="Shown once; the invitee opens the invitation with it")


class MoveReport(BaseModel):
    files: list[MoveFileReport]
    committed: bool
    batch_id: UUID | None
    undo_until: datetime | None
    invitations: list[MoveInvitation]


@dataclass
class LoadedFile:
    id: UUID
    business_file: UUID | None
    filename: str
    kind: str | None
    mapping: list[str | None]


@dataclass
class Tally:
    rows: int = 0
    ready: int = 0
    duplicates: int = 0
    invalid: int = 0
    skipped: int = 0
    issues: list[MoveIssue] = field(default_factory=list)
    sample: list[dict[str, str]] = field(default_factory=list)

    def bad(self, line: int, field_name: str | None, code: str, *, kind: str = "invalid") -> None:
        setattr(self, kind, getattr(self, kind) + 1)
        self.issues.append(MoveIssue(line=line, field=field_name, code=code))

    def ok(self, example: dict[str, str]) -> None:
        self.ready += 1
        if len(self.sample) < 5:
            self.sample.append(example)


def _name_key(first_name: str, last_name: str | None) -> str:
    return " ".join(f"{first_name} {last_name or ''}".lower().split())


class ClientIndex:
    """Finds a client by email, then phone, then full name (a name shared by two is ambiguous)."""

    def __init__(self, db: Session) -> None:
        self.emails: dict[str, UUID] = {}
        self.phones: dict[str, UUID] = {}
        self.names: dict[str, list[UUID]] = {}
        rows = db.execute(
            text("SELECT id, lower(email), phone, first_name, last_name FROM app.clients")
        ).all()
        for client_id, email, phone, first, last in rows:
            if email:
                self.emails[email] = client_id
            if phone and phone_key(phone):
                self.phones[phone_key(phone)] = client_id
            self.names.setdefault(_name_key(first, last), []).append(client_id)

    def find(self, person: dict) -> tuple[UUID | None, str]:
        if person.get("email") and person["email"].lower() in self.emails:
            return self.emails[person["email"].lower()], ""
        if person.get("phone") and phone_key(person["phone"]) in self.phones:
            return self.phones[phone_key(person["phone"])], ""
        if person.get("name"):
            found = self.names.get(_name_key(person["name"], None), [])
            if len(found) == 1:
                return found[0], ""
            if len(found) > 1:
                return None, "client_ambiguous"
        return None, "client_not_found"


class Mover:
    def __init__(self, db: Session, tenant_id: UUID, session_id: UUID, role: str) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.role = role
        tenant = db.execute(
            text("SELECT time_zone, currency FROM app.tenants WHERE id = :t"), {"t": tenant_id}
        ).one()
        self.zone = ZoneInfo(tenant.time_zone)
        self.currency = tenant.currency
        self.today: date = datetime.now(self.zone).date()
        self.batch_id = uuid4()
        self.items: list[dict] = []
        self.invitations: list[MoveInvitation] = []
        self._index: ClientIndex | None = None
        self._services: dict[str, dict] | None = None
        self._plans: dict[tuple[str, str], UUID] | None = None

    # -- helpers ------------------------------------------------------------------------------

    def _item(self, entity: str, entity_id: UUID) -> None:
        self.items.append({"entity": entity, "entity_id": entity_id})

    def _clients(self) -> ClientIndex:
        if self._index is None:
            self._index = ClientIndex(self.db)
        return self._index

    def _service_map(self) -> dict[str, dict]:
        if self._services is None:
            rows = self.db.execute(
                text("SELECT id, lower(name), duration_minutes, capacity FROM app.services")
            ).all()
            self._services = {
                name: {"id": sid, "duration": minutes, "capacity": capacity}
                for sid, name, minutes, capacity in rows
            }
        return self._services

    # -- the run ------------------------------------------------------------------------------

    def run(self, files: list[LoadedFile]) -> list[MoveFileReport]:
        self.db.execute(
            text("""
                INSERT INTO app.import_batches (id, tenant_id, session_id, undo_until, created_by)
                VALUES (:id, :t, :s, now() + make_interval(days => :days), app.current_user_id())
            """),
            {"id": self.batch_id, "t": self.tenant_id, "s": self.session_id, "days": UNDO_DAYS},
        )
        reports: list[MoveFileReport] = []
        for kind in KINDS_IN_ORDER:
            for loaded in files:
                if loaded.kind != kind:
                    continue
                reports.append(self._file(loaded))
        for loaded in files:
            if loaded.kind is None:
                reports.append(
                    MoveFileReport(
                        import_file_id=loaded.id,
                        filename=loaded.filename,
                        kind=None,
                        rows=0,
                        ready=0,
                        duplicates=0,
                        invalid=0,
                        skipped=0,
                        issues=[],
                        sample=[],
                    )
                )
        if self.items:
            self.db.execute(
                text("""
                    INSERT INTO app.import_batch_items (tenant_id, batch_id, entity, entity_id)
                    VALUES (:t, :b, :entity, :entity_id)
                """),
                [{"t": self.tenant_id, "b": self.batch_id, **item} for item in self.items],
            )
        counts: dict[str, int] = {}
        for report in reports:
            if report.kind:
                counts[report.kind] = counts.get(report.kind, 0) + report.ready
        self.db.execute(
            text("UPDATE app.import_batches SET counts = CAST(:c AS jsonb) WHERE id = :id"),
            {"c": json.dumps(counts), "id": self.batch_id},
        )
        return reports

    def _file(self, loaded: LoadedFile) -> MoveFileReport:
        tally = Tally()
        row = (
            self.db.execute(
                text("""
                    SELECT content, storage_key, encrypted FROM app.business_files WHERE id = :id
                """),
                {"id": loaded.business_file},
            )
            .mappings()
            .first()
            if loaded.business_file
            else None
        )
        if row is None:
            tally.bad(0, None, "file_expired")
        else:
            try:
                table = read_table(read_file(self.db, dict(row)), loaded.filename, MAX_FILE_BYTES)
            except ImportFileError as error:
                tally.bad(0, None, error.code)
            else:
                parsed = parse(loaded.kind or "", table, loaded.mapping)
                tally.rows = len(parsed)
                getattr(self, f"do_{loaded.kind}")(parsed, tally)
        return MoveFileReport(
            import_file_id=loaded.id,
            filename=loaded.filename,
            kind=loaded.kind,
            rows=tally.rows,
            ready=tally.ready,
            duplicates=tally.duplicates,
            invalid=tally.invalid,
            skipped=tally.skipped,
            issues=tally.issues[:MAX_ISSUES],
            sample=tally.sample,
        )

    # -- one kind at a time (`do_<kind>`, picked by `_file`) -------------------------------------

    def do_services(self, rows: list, tally: Tally) -> None:
        known = self._service_map()
        new: list[dict] = []
        for row in rows:
            if row.errors:
                for name, code in row.errors:
                    tally.bad(row.line, name, code)
                continue
            key = row.values["name"].lower()
            if key in known:
                tally.bad(row.line, "name", "duplicate", kind="duplicates")
                continue
            service_id = uuid4()
            known[key] = {
                "id": service_id,
                "duration": row.values["duration_minutes"],
                "capacity": row.values["capacity"],
            }
            new.append({**row.values, "id": service_id})
            self._item("service", service_id)
            tally.ok({"name": row.values["name"]})
        if new:
            self.db.execute(
                text("""
                    INSERT INTO app.services (id, tenant_id, name, description, duration_minutes,
                                              capacity, price_amount, price_currency)
                    VALUES (:id, :t, :name, :description, :duration_minutes, :capacity,
                            :price_amount, :currency)
                """),
                [{**v, "t": self.tenant_id, "currency": self.currency} for v in new],
            )

    def do_staff(self, rows: list, tally: Tally) -> None:
        taken = {
            email
            for email in self.db.execute(
                text("""
                    SELECT lower(u.email) FROM app.tenant_members m
                    JOIN app.users u ON u.id = m.user_id
                    UNION SELECT lower(email) FROM app.invitations WHERE accepted_at IS NULL
                """)
            ).scalars()
        }
        new: list[dict] = []
        for row in rows:
            if row.errors:
                for name, code in row.errors:
                    tally.bad(row.line, name, code)
                continue
            email = row.values["email"].lower()
            if email in taken:
                tally.bad(row.line, "email", "duplicate", kind="duplicates")
                continue
            taken.add(email)
            token = secrets.token_urlsafe(32)
            invitation_id = uuid4()
            new.append(
                {
                    "id": invitation_id,
                    "email": row.values["email"],
                    "role": row.values["role"],
                    "hash": hashlib.sha256(token.encode()).hexdigest(),
                }
            )
            self.invitations.append(
                MoveInvitation(email=row.values["email"], role=row.values["role"], token=token)
            )
            self._item("invitation", invitation_id)
            tally.ok({"email": row.values["email"], "role": row.values["role"]})
        if new:
            self.db.execute(
                text("""
                    INSERT INTO app.invitations
                        (id, tenant_id, email, role, token_hash, invited_by, expires_at)
                    VALUES (:id, :t, :email, :role, :hash, app.current_user_id(),
                            now() + make_interval(days => :days))
                """),
                [{**v, "t": self.tenant_id, "days": INVITATION_DAYS} for v in new],
            )

    def do_clients(self, rows: list, tally: Tally) -> None:
        index = self._clients()
        new: list[dict] = []
        for row in rows:
            if row.errors:
                for name, code in row.errors:
                    tally.bad(row.line, name, code)
                continue
            values = row.values
            email = (values["email"] or "").lower()
            phone = phone_key(values["phone"] or "")
            name = _name_key(values["first_name"], values["last_name"])
            # Without an email or phone, the same full name is the only hint of a duplicate.
            if (
                (email and email in index.emails)
                or (phone and phone in index.phones)
                or (not email and not phone and name in index.names)
            ):
                tally.bad(row.line, None, "duplicate", kind="duplicates")
                continue
            client_id = uuid4()
            if email:
                index.emails[email] = client_id
            if phone:
                index.phones[phone] = client_id
            index.names.setdefault(name, []).append(client_id)
            new.append({**values, "id": client_id})
            self._item("client", client_id)
            tally.ok(
                {"name": f"{values['first_name']} {values['last_name'] or ''}".strip()}
                | ({"email": values["email"]} if values["email"] else {})
            )
        if new:
            self.db.execute(
                text("""
                    INSERT INTO app.clients
                        (id, tenant_id, first_name, last_name, email, phone, date_of_birth, notes,
                         status, source)
                    VALUES (:id, :t, :first_name, :last_name, :email, :phone, :date_of_birth,
                            :notes, :status, 'other')
                """),
                [{**v, "t": self.tenant_id} for v in new],
            )

    def _plan(self, name: str, kind: str, row: dict, start: date, end: date) -> UUID:
        if self._plans is None:
            self._plans = {
                (plan_name, plan_kind): plan_id
                for plan_id, plan_name, plan_kind in self.db.execute(
                    text("SELECT id, lower(name), kind FROM app.plans")
                )
            }
        key = (name.lower(), kind)
        if key in self._plans:
            return self._plans[key]
        plan_id = uuid4()
        self._plans[key] = plan_id
        validity = max(1, min(1095, (end - start).days + 1))
        self.db.execute(
            text("""
                INSERT INTO app.plans (id, tenant_id, name, description, kind, price_amount,
                                       price_currency, validity_days, credits, active)
                VALUES (:id, :t, :name, 'Imported from the previous system', :kind, :price,
                        :currency, :validity, :credits, false)
            """),
            {
                "id": plan_id,
                "t": self.tenant_id,
                "name": name,
                "kind": kind,
                "price": row["price_amount"],
                "currency": self.currency,
                "validity": validity,
                "credits": row["credits"] if kind == "punch_card" else None,
            },
        )
        self._item("plan", plan_id)
        return plan_id

    def do_memberships(self, rows: list, tally: Tally) -> None:
        index = self._clients()
        have = {
            (client_id, plan_id, ends_on)
            for client_id, plan_id, ends_on in self.db.execute(
                text("SELECT client_id, plan_id, ends_on FROM app.entitlements")
            )
        }
        new: list[dict] = []
        for row in rows:
            if row.errors:
                for name, code in row.errors:
                    tally.bad(row.line, name, code)
                continue
            values = row.values
            client_id, problem = index.find(values["client"])
            if client_id is None:
                tally.bad(row.line, "client_name", problem)
                continue
            credits, ends_on = values["credits"], values["ends_on"]
            if credits == 0:
                tally.bad(row.line, "credits_left", "empty_balance", kind="skipped")
                continue
            if ends_on < self.today:
                tally.bad(row.line, "ends_on", "expired", kind="skipped")
                continue
            starts_on = values["starts_on"] or min(self.today, ends_on)
            if starts_on > ends_on:
                tally.bad(row.line, "starts_on", "invalid_date")
                continue
            kind = "punch_card" if credits is not None else "membership"
            if credits is not None and credits > 1000:
                tally.bad(row.line, "credits_left", "invalid_number")
                continue
            plan_id = self._plan(values["plan_name"], kind, values, starts_on, ends_on)
            if (client_id, plan_id, ends_on) in have:
                tally.bad(row.line, None, "duplicate", kind="duplicates")
                continue
            have.add((client_id, plan_id, ends_on))
            entitlement_id = uuid4()
            new.append(
                {
                    "id": entitlement_id,
                    "client": client_id,
                    "plan": plan_id,
                    "name": values["plan_name"],
                    "kind": kind,
                    "credits": credits,
                    "starts_on": starts_on,
                    "ends_on": ends_on,
                    "price": values["price_amount"],
                }
            )
            self._item("entitlement", entitlement_id)
            example = {"plan": values["plan_name"], "until": ends_on.isoformat()}
            if credits is not None:
                example["left"] = str(credits)
            tally.ok(example)
        if new:
            self.db.execute(
                text("""
                    INSERT INTO app.entitlements
                        (id, tenant_id, client_id, plan_id, name, kind, credits, starts_on,
                         ends_on, price_amount, price_currency)
                    VALUES (:id, :t, :client, :plan, :name, :kind, :credits, :starts_on, :ends_on,
                            :price, :currency)
                """),
                [{**v, "t": self.tenant_id, "currency": self.currency} for v in new],
            )

    def do_appointments(self, rows: list, tally: Tally) -> None:
        index = self._clients()
        services = self._service_map()
        now = datetime.now(UTC)
        sessions: dict[tuple[UUID, datetime], dict] = {
            (row.service_id, row.starts_at): {"id": row.id, "capacity": row.capacity, "booked": 0}
            for row in self.db.execute(
                text("""
                    SELECT id, service_id, starts_at, capacity FROM app.sessions
                    WHERE status = 'scheduled' AND starts_at > now()
                """)
            )
        }
        by_id = {s["id"]: s for s in sessions.values()}
        booked: set[tuple[UUID, UUID]] = set()
        for session_id, client_id in self.db.execute(
            text("""
                SELECT b.session_id, b.client_id FROM app.bookings b
                JOIN app.sessions s ON s.id = b.session_id
                WHERE b.status <> 'cancelled' AND s.starts_at > now()
            """)
        ):
            booked.add((session_id, client_id))
            if session_id in by_id:
                by_id[session_id]["booked"] += 1
        new_sessions: list[dict] = []
        new_bookings: list[dict] = []
        for row in rows:
            if row.errors:
                for name, code in row.errors:
                    tally.bad(row.line, name, code)
                continue
            values = row.values
            client_id, problem = index.find(values["client"])
            if client_id is None:
                tally.bad(row.line, "client_name", problem)
                continue
            service = services.get(values["service_name"].lower())
            if service is None:
                tally.bad(row.line, "service_name", "service_not_found")
                continue
            starts_at = values["starts_at"].replace(tzinfo=self.zone).astimezone(UTC)
            if starts_at <= now:
                tally.bad(row.line, "starts_at", "past", kind="skipped")
                continue
            slot = sessions.get((service["id"], starts_at))
            if slot is None:
                slot = {"id": uuid4(), "capacity": service["capacity"], "booked": 0}
                sessions[(service["id"], starts_at)] = slot
                minutes = values["duration_minutes"] or service["duration"]
                new_sessions.append(
                    {
                        "id": slot["id"],
                        "service": service["id"],
                        "capacity": slot["capacity"],
                        "starts_at": starts_at,
                        "ends_at": starts_at + timedelta(minutes=minutes),
                    }
                )
                self._item("session", slot["id"])
            if (slot["id"], client_id) in booked:
                tally.bad(row.line, None, "duplicate", kind="duplicates")
                continue
            if slot["booked"] >= slot["capacity"]:
                tally.bad(row.line, "starts_at", "session_full")
                continue
            slot["booked"] += 1
            booked.add((slot["id"], client_id))
            booking_id = uuid4()
            new_bookings.append({"id": booking_id, "session": slot["id"], "client": client_id})
            self._item("booking", booking_id)
            tally.ok(
                {
                    "service": values["service_name"],
                    "at": values["starts_at"].strftime("%Y-%m-%d %H:%M"),
                }
            )
        if new_sessions:
            self.db.execute(
                text("""
                    INSERT INTO app.sessions
                        (id, tenant_id, service_id, capacity, starts_at, ends_at)
                    VALUES (:id, :t, :service, :capacity, :starts_at, :ends_at)
                """),
                [{**v, "t": self.tenant_id} for v in new_sessions],
            )
        if new_bookings:
            self.db.execute(
                text("""
                    INSERT INTO app.bookings (id, tenant_id, session_id, client_id, status,
                                              created_by)
                    VALUES (:id, :t, :session, :client, 'booked', app.current_user_id())
                """),
                [{**v, "t": self.tenant_id} for v in new_bookings],
            )


KINDS_IN_ORDER = ("services", "staff", "clients", "memberships", "appointments")
assert set(KINDS_IN_ORDER) == set(KINDS)
