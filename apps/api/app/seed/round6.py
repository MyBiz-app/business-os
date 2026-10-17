"""What round 6 adds to a demo business: pay setup, approved hours, a payroll run, and a move.

For each demo business it gives a few team members pay terms (monthly and hourly), a month of
clock-in hours that the manager has approved, the month's payroll run (worked out by the same
code the API uses, so the numbers and warnings are real), and, for the gym, a half-finished
"Move to MyBiz" session with an Excel export of a previous system waiting to be checked.

It only adds and is safe to run again: people who already have terms, a month that already has
hours or a run, and a move session that already exists are left alone. Nothing is sent to anyone;
the move is a draft that is not imported.
"""

import io
import json
import random
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, time, timedelta
from uuid import UUID

from openpyxl import Workbook
from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.api.payroll_runs import _refresh
from app.files import store_file, system_folder_id
from app.migration.fields import guess_kind, suggest_mapping
from app.migration.formats import read_any
from app.schedule.scheduling import local_to_utc

GYM_NETWORK = "Adir fitness"
MOVE_ORIGIN = "Previous system (demo)"
MOVE_FILE = "previous-system-clients.xlsx"
WORK_WEEKDAYS = {6, 0, 1, 2, 3}  # Sunday to Thursday
TEAM_SIZE = 4

# (employment type, monthly pay, hourly rate), in minor units (agorot) of the business currency.
PAY_TERMS = (
    ("global", 1_150_000, 6_500),
    ("hourly", None, 5_200),
    ("global_overtime", 980_000, 5_800),
    ("hourly", None, 6_100),
)
PENSION = {"fund_name": "Demo pension fund", "employee_pct": 6, "employer_pct": 6.5,
           "severance_pct": 6}  # fmt: skip
STUDY_FUND = {"fund_name": "Demo study fund", "employee_pct": 2.5, "employer_pct": 7.5}

# Fictitious clients of a previous system. One repeats a phone and one has a broken email, so the
# check shows what it reports before anything is imported.
MOVE_HEADERS = ["שם פרטי", "שם משפחה", "טלפון", "דוא״ל", "תאריך לידה", "הערות"]
MOVE_ROWS = [
    ("נועה", "אלון", "0501234001", "noa.alon@example.com", "1991-03-14", "מנוי חודשי"),
    ("יעל", "ברק", "0501234002", "yael.barak@example.com", "1988-11-02", ""),
    ("דניאל", "גולן", "0501234003", "daniel.golan@example.com", "1995-07-21", "פגיעת ברך"),
    ("מאיה", "דגן", "0501234004", "maya.dagan@example.com", "1993-01-30", ""),
    ("איתי", "הראל", "0501234005", "itay.harel@example.com", "1986-09-09", "כרטיסייה"),
    ("שירה", "וינר", "0501234006", "shira.wiener@example.com", "1999-05-17", ""),
    ("עומר", "זיו", "0501234007", "omer.ziv@example.com", "1990-12-25", ""),
    ("הדר", "חביב", "0501234008", "hadar.haviv@example.com", "1994-04-04", "מנוי שנתי"),
    ("גיא", "טל", "0501234009", "guy.tal@example.com", "1987-08-18", ""),
    ("ליה", "כרמי", "0501234010", "lia.carmi@example.com", "2000-02-11", ""),
    ("רועי", "לוין", "0501234011", "roee.levin@example.com", "1992-06-06", ""),
    ("דנה", "מלכה", "0501234001", "dana.malka@example.com", "1996-10-23", "אותו טלפון"),
    ("אסף", "נחום", "0501234013", "asaf-nahum-at-example", "1989-03-03", "מייל שגוי"),
    ("תמר", "סגל", "0501234014", "tamar.segal@example.com", "1997-09-12", ""),
]


@contextmanager
def _as_tenant(conn: Connection, tenant_id: UUID, user_id: UUID) -> Iterator[Session]:
    """A session that sees one business the way the API does (the app role, row security on)."""
    conn.execute(text("SET LOCAL ROLE app_api"))
    conn.execute(
        text("SELECT set_config('app.user_id', :u, true), set_config('app.tenant_id', :t, true)"),
        {"u": str(user_id), "t": str(tenant_id)},
    )
    session = Session(bind=conn)
    try:
        yield session
        session.flush()
    finally:
        session.close()
        conn.execute(text("RESET ROLE"))


def _month(today: date) -> date:
    """The month to fill: this one, or the last one in its first days (nothing to work out yet)."""
    first = today.replace(day=1)
    return (first - timedelta(days=1)).replace(day=1) if today.day < 8 else first


def _team(conn: Connection, tenant_id: UUID) -> list[tuple[UUID, UUID]]:
    """Up to TEAM_SIZE team members who are not owners, each with the branch they work at."""
    default = conn.execute(
        text("SELECT id FROM app.locations WHERE tenant_id = :t ORDER BY created_at LIMIT 1"),
        {"t": tenant_id},
    ).scalar_one()
    rows = conn.execute(
        text("""
            SELECT m.user_id, coalesce(m.home_location_id, m.location_ids[1], :default)
            FROM app.tenant_members m JOIN app.users u ON u.id = m.user_id
            WHERE m.tenant_id = :t AND m.role <> 'owner' AND u.email LIKE '%@example.invalid'
            ORDER BY m.created_at, m.user_id LIMIT :n
        """),
        {"t": tenant_id, "default": default, "n": TEAM_SIZE},
    ).all()
    return [(user, location) for user, location in rows]


def _pay_setup(conn: Connection, tenant_id: UUID, currency: str, team: list) -> int:
    added = 0
    for (user_id, location), (kind, monthly, hourly) in zip(team, PAY_TERMS, strict=False):
        added += conn.execute(
            text("""
                INSERT INTO app.employment_profiles
                    (tenant_id, user_id, employment_type, currency, monthly_amount_minor,
                     hourly_rate_minor, start_date, work_days_per_week, billing_location_id,
                     pension, study_fund)
                VALUES (:t, :u, :kind, :currency, :monthly, :hourly, '2025-01-01', 5, :l,
                        CAST(:pension AS jsonb), CAST(:study AS jsonb))
                ON CONFLICT (tenant_id, user_id) DO NOTHING
            """),
            {
                "t": tenant_id,
                "u": user_id,
                "kind": kind,
                "currency": currency,
                "monthly": monthly,
                "hourly": hourly,
                "l": location,
                "pension": json.dumps(PENSION),
                "study": json.dumps(STUDY_FUND),
            },
        ).rowcount
    return added


def _hours(
    conn: Connection, tenant_id: UUID, owner: UUID, team: list, month: date, today: date,
    time_zone: str, rng: random.Random,
) -> int:  # fmt: skip
    """A clock-in and clock-out for each working day of the month so far, then the owner's
    approval of the month for each person. A person who already has hours that month is skipped."""
    entries = 0
    for user_id, location in team:
        has = conn.execute(
            text("""
                SELECT 1 FROM app.time_clock_entries
                WHERE tenant_id = :t AND user_id = :u AND clock_in >= :from AND clock_in < :to
            """),
            {"t": tenant_id, "u": user_id, "from": month, "to": month + timedelta(days=32)},
        ).first()
        if has:
            continue
        day = month
        while day < today and day.month == month.month:
            if day.weekday() in WORK_WEEKDAYS:
                start = time(8, rng.choice((0, 15, 30)))
                length = rng.choice((8, 8, 8, 9, 9, 10))  # now and then a long day
                clock_in = local_to_utc(day, start, time_zone)
                conn.execute(
                    text("""
                        INSERT INTO app.time_clock_entries
                            (tenant_id, user_id, location_id, clock_in, clock_out)
                        VALUES (:t, :u, :l, :in, :out)
                    """),
                    {
                        "t": tenant_id,
                        "u": user_id,
                        "l": location,
                        "in": clock_in,
                        "out": clock_in + timedelta(hours=length, minutes=rng.choice((0, 20, 40))),
                    },
                )
                entries += 1
            day += timedelta(days=1)
        conn.execute(
            text("""
                INSERT INTO app.time_clock_approvals (tenant_id, user_id, month, approved_by)
                VALUES (:t, :u, :month, :by) ON CONFLICT DO NOTHING
            """),
            {"t": tenant_id, "u": user_id, "month": month, "by": owner},
        )
    return entries


def _payroll_run(conn: Connection, tenant_id: UUID, owner: UUID, currency: str, month: date) -> int:
    """The month's run with every line worked out; nothing is approved or paid."""
    with _as_tenant(conn, tenant_id, owner) as session:
        run_id = session.execute(
            text("""
                INSERT INTO app.payroll_runs (tenant_id, period, currency, created_by)
                VALUES (:t, :month, :currency, :by) ON CONFLICT (tenant_id, period) DO NOTHING
                RETURNING id
            """),
            {"t": tenant_id, "month": month, "currency": currency, "by": owner},
        ).scalar()
        if run_id is None:
            return 0
        _refresh(session, tenant_id, run_id, month)
    return 1


def _xlsx() -> bytes:
    book = Workbook()
    sheet = book.active
    sheet.title = "Clients"
    sheet.append(MOVE_HEADERS)
    for row in MOVE_ROWS:
        sheet.append(list(row))
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def _move_session(conn: Connection, tenant_id: UUID, owner: UUID, time_zone: str) -> int:
    """A draft move with an Excel export of clients, mapped and ready to check and import."""
    exists = conn.execute(
        text("SELECT 1 FROM app.import_sessions WHERE tenant_id = :t AND origin = :o"),
        {"t": tenant_id, "o": MOVE_ORIGIN},
    ).first()
    if exists:
        return 0
    data = _xlsx()
    table = read_any(data, MOVE_FILE, len(data) + 1, time_zone)
    headers = table[0]
    kind = guess_kind(headers)
    mapping = suggest_mapping(kind, headers) if kind else [None] * len(headers)
    with _as_tenant(conn, tenant_id, owner) as db:
        session_id = db.execute(
            text("""
                INSERT INTO app.import_sessions (tenant_id, origin, created_by)
                VALUES (:t, :origin, :by) RETURNING id
            """),
            {"t": tenant_id, "origin": MOVE_ORIGIN, "by": owner},
        ).scalar_one()
        stored = store_file(
            db,
            tenant_id,
            system_folder_id(db, tenant_id, "imports"),
            name=MOVE_FILE,
            content=data,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        db.execute(
            text("""
                INSERT INTO app.import_files
                    (tenant_id, session_id, file_id, filename, kind, headers, mapping, row_count)
                VALUES (:t, :s, :f, :name, :kind, CAST(:headers AS jsonb),
                        CAST(:mapping AS jsonb), :rows)
            """),
            {
                "t": tenant_id,
                "s": session_id,
                "f": stored["id"],
                "name": MOVE_FILE,
                "kind": kind,
                "headers": json.dumps(
                    [
                        {"name": name, "example": next((r[i] for r in table[1:] if r[i]), "")[:80]}
                        for i, name in enumerate(headers)
                    ],
                    ensure_ascii=False,
                ),
                "mapping": json.dumps(mapping),
                "rows": len(table) - 1,
            },
        )
    return 1


def seed_round6(conn: Connection, tenant_id: UUID, tenant_name: str, today: date) -> dict[str, int]:
    """Adds the round-6 demo data to one business; returns what was added."""
    owner = conn.execute(
        text("""
            SELECT user_id FROM app.tenant_members
            WHERE tenant_id = :t AND role = 'owner' ORDER BY created_at LIMIT 1
        """),
        {"t": tenant_id},
    ).scalar_one()
    currency, time_zone = conn.execute(
        text("SELECT currency, time_zone FROM app.tenants WHERE id = :t"), {"t": tenant_id}
    ).one()
    team = _team(conn, tenant_id)
    month = _month(today)
    rng = random.Random(tenant_id.int)
    counts = {"pay_setups": 0, "time_entries": 0, "payroll_runs": 0, "move_sessions": 0}
    if team:
        counts["pay_setups"] = _pay_setup(conn, tenant_id, currency, team)
        counts["time_entries"] = _hours(conn, tenant_id, owner, team, month, today, time_zone, rng)
        counts["payroll_runs"] = _payroll_run(conn, tenant_id, owner, currency, month)
    if tenant_name == GYM_NETWORK:
        counts["move_sessions"] = _move_session(conn, tenant_id, owner, time_zone)
    return counts
