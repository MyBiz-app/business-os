"""Round 5 on a demo business: the AI team, spend, scheduled tasks, branch groups, branch
managers, the content studio and contact emails.

Nothing here calls an outside service: social numbers come from the demo provider, AI usage is
written as past usage events, and scheduled-task runs are history rows."""

import json
import random
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import Connection, text

from app.ai.scheduled import next_run
from app.schedule.scheduling import local_to_utc
from app.seed.common import TIME_ZONE
from app.social.demo import DEMO
from app.social.providers import AccountInfo
from app.social.sync import add_account, sync_account

# How the month's AI credits were spent, by agent (relative weights).
AGENT_USAGE = (
    ("chief", 4),
    ("secretary", 9),
    ("marketing", 6),
    ("sales", 4),
    ("finance", 3),
    ("creative", 5),
)
MODELS = (("claude-sonnet-5-5", 0.8), ("claude-haiku-5-5", 0.2))

DRAFTS = (
    ("instagram", "draft", "שבוע חדש, שיעורים חדשים. מחכים לכם!", "הכרזה על שיעורים חדשים"),
    ("facebook", "draft", "פתחנו מקומות חדשים בשיעורי הבוקר. כדאי להספיק להירשם.", None),
    ("instagram", "published", "מאחורי הקלעים: ככה נראה בוקר אצלנו.", "מאחורי הקלעים"),
)


def _groups(conn: Connection, tenant_id: UUID, branches: list[UUID]) -> None:
    """Two groups of branches (a business with a single branch has none)."""
    if len(branches) < 2:
        return
    half = (len(branches) + 1) // 2
    for name, members in (("מרכז", branches[:half]), ("צפון", branches[half:])):
        if not members:
            continue
        group_id = conn.execute(
            text("INSERT INTO app.location_groups (tenant_id, name) VALUES (:t, :n) RETURNING id"),
            {"t": tenant_id, "n": name},
        ).scalar_one()
        for branch in members:
            conn.execute(
                text("""
                    INSERT INTO app.location_group_members (tenant_id, group_id, location_id)
                    VALUES (:t, :g, :l)
                """),
                {"t": tenant_id, "g": group_id, "l": branch},
            )


def _branch_manager(conn: Connection, tenant_id: UUID, branches: list[UUID],
                    staff: dict[UUID, list[UUID]]) -> None:  # fmt: skip
    """The first branch's first staff member becomes its branch manager (multi-branch only)."""
    if len(branches) < 2 or not staff.get(branches[0]):
        return
    conn.execute(
        text("""
            UPDATE app.tenant_members SET role = 'branch_manager', location_ids = :branches
            WHERE tenant_id = :t AND user_id = :u
        """),
        {"t": tenant_id, "u": staff[branches[0]][0], "branches": [branches[0]]},
    )
    conn.execute(
        text("UPDATE app.locations SET manager_user_id = :u WHERE id = :l"),
        {"u": staff[branches[0]][0], "l": branches[0]},
    )


def _agents(conn: Connection, tenant_id: UUID, owner: UUID, has_groups: bool) -> None:
    """A built-in agent changed for this business, and a custom one."""
    group_ids = (
        conn.execute(
            text("""
                SELECT id FROM app.location_groups WHERE tenant_id = :t ORDER BY sort_order, name
            """),
            {"t": tenant_id},
        )
        .scalars()
        .all()
        if has_groups
        else []
    )
    conn.execute(
        text("""
            INSERT INTO app.ai_agents (tenant_id, builtin_key, tone, location_scope,
                                       location_group_ids, created_by)
            VALUES (:t, 'finance', 'formal', :scope, :groups, :owner)
        """),
        {
            "t": tenant_id,
            "scope": "groups" if group_ids else "all",
            "groups": group_ids[:1],
            "owner": owner,
        },
    )
    conn.execute(
        text("""
            INSERT INTO app.ai_agents
                (tenant_id, name, role_title, color, topic, instructions, tone, tool_domains,
                 allowed_roles, model_tier, created_by)
            VALUES (:t, 'דנה', 'קבלה ושיבוצים', '#F59E0B',
                    'Front desk: today''s schedule, check-ins and quick client lookups.',
                    'You help the front desk: today''s sessions, who is booked and quick lookups. '
                    'Keep answers short.',
                    'short', ARRAY['schedule', 'bookings', 'clients', 'tasks'],
                    ARRAY['owner', 'manager', 'branch_manager', 'front_desk'], 'fast', :owner)
        """),
        {"t": tenant_id, "owner": owner},
    )


def _spend(conn: Connection, tenant_id: UUID, owner: UUID, staff: list[UUID], today: date,
           rng: random.Random) -> None:  # fmt: skip
    """A month of AI usage by agent and person, a limit for the front desk and one for a person."""
    people = [owner, *staff[:3]]
    rows = []
    for day_offset in range(30):
        day = today - timedelta(days=day_offset)
        for agent_key, weight in AGENT_USAGE:
            if rng.random() > 0.55:
                continue
            model = rng.choices([m for m, _ in MODELS], weights=[w for _, w in MODELS])[0]
            tokens_in = rng.randint(900, 5200)
            rows.append(
                {
                    "t": tenant_id,
                    "quantity": round(weight * rng.uniform(0.2, 0.8), 4),
                    "details": json.dumps(
                        {
                            "agent_key": agent_key,
                            "user_id": str(rng.choice(people)),
                            "model": model,
                            "input_tokens": tokens_in,
                            "output_tokens": tokens_in // 9,
                            "cache_read_tokens": 0,
                            "cache_write_tokens": 0,
                        }
                    ),
                    "at": local_to_utc(
                        day, time(rng.randint(8, 21), rng.randint(0, 59)), TIME_ZONE
                    ),
                }
            )
    for row in rows:
        conn.execute(
            text("""
                INSERT INTO app.usage_events (tenant_id, meter, quantity, details, source_ref,
                                              occurred_at)
                VALUES (:t, 'ai_credits', :quantity, CAST(:details AS jsonb), 'seed', :at)
            """),
            row,
        )
    conn.execute(
        text("""
            INSERT INTO app.ai_credit_limits (tenant_id, subject_kind, subject_key, monthly_credits)
            VALUES (:t, 'role', 'front_desk', 40), (:t, 'role', 'staff', 25)
        """),
        {"t": tenant_id},
    )
    conn.execute(
        text("INSERT INTO app.tenant_ai_settings (tenant_id, payg_enabled) VALUES (:t, false)"),
        {"t": tenant_id},
    )


def _tasks(conn: Connection, tenant_id: UUID, owner: UUID, today: date) -> None:
    """Scheduled tasks: a weekly summary (with past runs), a paused daily one and a finished
    one-off. The weekly one runs for real on staging, capped at five credits."""
    now = datetime.now(UTC)
    weekly = {"type": "weekly", "time": "08:00", "weekdays": [6]}
    daily = {"type": "daily", "time": "07:30"}
    once = {"type": "once", "time": "09:00", "date": (today - timedelta(days=9)).isoformat()}
    specs = (
        ("sales", "סיכום שבועי של מכירות", "Send me a short weekly sales summary with the "
         "numbers that changed.", weekly, "active", next_run(weekly, TIME_ZONE, now), 5),
        ("marketing", "לידים שלא נענו", "List leads nobody answered for 3 days and draft a "
         "short reply for each.", daily, "paused", None, 5),
        ("chief", "בדיקת פתיחה לשבוע", "Check next week's schedule for empty classes.", once,
         "done", None, 5),
    )  # fmt: skip
    for agent, title, instruction, schedule, status, upcoming, cap in specs:
        task_id = conn.execute(
            text("""
                INSERT INTO app.ai_scheduled_tasks
                    (tenant_id, created_by, agent_key, kind, title, instruction, schedule,
                     time_zone, next_run_at, last_run_at, status, max_credits)
                VALUES (:t, :owner, :agent, 'agent_run', :title, :instruction,
                        CAST(:schedule AS jsonb), :zone, :next, :last, :status, :cap)
                RETURNING id
            """),
            {
                "t": tenant_id,
                "owner": owner,
                "agent": agent,
                "title": title,
                "instruction": instruction,
                "schedule": json.dumps(schedule),
                "zone": TIME_ZONE,
                "next": upcoming,
                "last": now - timedelta(days=7) if status == "active" else None,
                "status": status,
                "cap": cap,
            },
        ).scalar_one()
        if status != "active":
            continue
        for weeks_ago, credits in ((3, 1.4), (2, 1.1), (1, 1.6)):
            started = now - timedelta(days=7 * weeks_ago)
            conn.execute(
                text("""
                    INSERT INTO app.ai_task_runs
                        (tenant_id, task_id, started_at, finished_at, status, credits, result)
                    VALUES (:t, :task, :start, :end, 'ok', :credits, CAST(:result AS jsonb))
                """),
                {
                    "t": tenant_id,
                    "task": task_id,
                    "start": started,
                    "end": started + timedelta(seconds=40),
                    "credits": credits,
                    "result": json.dumps({"summary": "Sales were steady; two plans renew soon.",
                                          "needs_approval": 0}),
                },
            )  # fmt: skip


def _content(conn: Connection, tenant_id: UUID, owner: UUID, branches: list[UUID]) -> None:
    """The content studio on the demo provider: five networks, a second branch Google profile
    in a multi-branch business, and a few drafts."""
    for info in DEMO.accounts():
        account_id = add_account(conn, tenant_id, DEMO.name, info, is_demo=True, connected_by=owner)
        sync_account(conn, tenant_id, account_id)
    if len(branches) > 1:
        account_id = add_account(
            conn,
            tenant_id,
            DEMO.name,
            AccountInfo(network="google_business", external_id="demo-google_business-2",
                        name="Demo google business (branch)"),
            is_demo=True,
            location_id=branches[1],
            connected_by=owner,
        )  # fmt: skip
        sync_account(conn, tenant_id, account_id)
    for network, status, body, idea in DRAFTS:
        conn.execute(
            text("""
                INSERT INTO app.social_drafts
                    (tenant_id, network, body, idea, status, created_by, agent_key, published_at)
                VALUES (:t, :network, :body, :idea, :status, :owner, 'creative',
                        CASE WHEN :status = 'published' THEN now() - interval '2 days' END)
            """),
            {"t": tenant_id, "network": network, "body": body, "idea": idea, "status": status,
             "owner": owner},
        )  # fmt: skip


def _emails(conn: Connection, tenant_id: UUID, branches: list[UUID], slug: str) -> None:
    """Reply-to addresses for the business and its first branch, and one still unverified.
    They never receive mail (reserved domain)."""
    rows = [(None, "reply_to", True), (None, "billing", False)]
    if len(branches) > 1:
        rows.append((branches[0], "reply_to", True))
    for location, purpose, verified in rows:
        scope = "branch" if location else "hello"
        conn.execute(
            text("""
                INSERT INTO app.contact_emails (tenant_id, location_id, purpose, email, verified_at)
                VALUES (:t, :l, :purpose, :email, CASE WHEN :verified THEN now() END)
            """),
            {
                "t": tenant_id,
                "l": location,
                "purpose": purpose,
                "email": f"{scope}-{purpose.replace('_', '')}@{slug}.example.invalid",
                "verified": verified,
            },
        )


def seed_agents(
    conn: Connection,
    tenant_id: UUID,
    owner: UUID,
    branches: list[UUID],
    staff: dict[UUID, list[UUID]],
    today: date,
    rng: random.Random,
    slug: str,
) -> None:
    """Fills one demo business with the round 5 features."""
    everyone = [u for members in staff.values() for u in members]
    _groups(conn, tenant_id, branches)
    _branch_manager(conn, tenant_id, branches, staff)
    _agents(conn, tenant_id, owner, has_groups=len(branches) > 1)
    _spend(conn, tenant_id, owner, everyone, today, rng)
    _tasks(conn, tenant_id, owner, today)
    _content(conn, tenant_id, owner, branches)
    _emails(conn, tenant_id, branches, slug)
