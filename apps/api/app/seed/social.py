"""The social layer and the sign-in accounts of the full demo.

    uv run python -m app.seed --owner-email you@example.com --demo full

After the four businesses exist, this connects the people around them:

* The owner's "plus" addresses (`you+manager@...`, `+branch`, `+coach`, `+barber`, `+clinic`)
  take over a demo team member of the right business, so their shifts, pay terms and classes
  come with them. An address that has not signed up yet is skipped; run again afterwards.
* The test customer (`<local>+cust@...`) and a friend (`+friend`) become clients of the
  businesses, with a membership about to end, a class tomorrow with two friends in it, a
  friend's invitation to another class and no health declaration yet.
* A group of people is a client of several businesses at once (one profile, a client record in
  each), so the owner sees one person across businesses.

Everything is idempotent. Nothing here ever touches the MyBiz primary owner's account.
"""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import Connection, text

from app.seed.guard import refuse_blocked_owner

GYM, TENNIS, BARBER, CLINIC = (
    "אדיר פיטנס",
    "טניס קלאב השרון",
    "בלייד ברברס",
    "מרחב - בריאות ותנועה",
)
TA_STRENGTH = "תל אביב - כוח"
RG_PILATES = "רמת גן - פילאטיס ויוגה"
HERZLIYA = "הרצליה"
FLORENTIN = "תל אביב - פלורנטין"
PETAH_TIKVA = "פתח תקווה - פיזיותרפיה"

# plus tag -> (business, branch or None for all, system role, display name, job title)
TEAM_LOGINS = {
    "manager": (GYM, None, "manager", "שירן לוי", "מנהלת רשת"),
    "branch": (GYM, TA_STRENGTH, "branch_manager", "ליאור כהן", "מנהל סניף"),
    "coach": (GYM, RG_PILATES, "staff", "נועה ברק", "מאמנת יוגה"),
    "barber": (BARBER, FLORENTIN, "staff", "רועי אביטל", "ספר"),
    "clinic": (CLINIC, PETAH_TIKVA, "front_desk", "מיכל דרור", "מזכירת קבלה"),
}
CUSTOMER_EMAIL = "adire7399+cust@gmail.com"  # a plain client: never an owner of anything
FRIEND_TAG = "friend"
# Where the test customer is a client: (business, home branch). The clinic is dormant.
CUSTOMER_HOMES = (
    (GYM, TA_STRENGTH),
    (TENNIS, HERZLIYA),
    (BARBER, FLORENTIN),
    (CLINIC, PETAH_TIKVA),
)
FRIEND_HOMES = ((GYM, TA_STRENGTH), (TENNIS, HERZLIYA))
SHARED_PEOPLE = 14  # clients of the gym who are also clients of the tennis club
SHARED_BARBER, SHARED_CLINIC = 8, 4  # of those, how many also go to the barber / the clinic


def plus_address(owner_email: str, tag: str) -> str:
    local, _, domain = owner_email.strip().lower().partition("@")
    return f"{local.split('+')[0]}+{tag}@{domain}"


def _tenants(conn: Connection, owner: UUID) -> dict[str, UUID]:
    return {
        name: tenant_id
        for tenant_id, name in conn.execute(
            text("""
                SELECT t.id, t.name FROM app.tenants t
                JOIN app.tenant_members m ON m.tenant_id = t.id AND m.role = 'owner'
                WHERE m.user_id = :u
            """),
            {"u": owner},
        ).all()
    }


def _branch(conn: Connection, tenant_id: UUID, name: str) -> UUID | None:
    return conn.execute(
        text("SELECT id FROM app.locations WHERE tenant_id = :t AND name = :n"),
        {"t": tenant_id, "n": name},
    ).scalar()


def _user(conn: Connection, email: str) -> UUID | None:
    if conn.execute(text("SELECT to_regclass('auth.users') IS NOT NULL")).scalar():
        conn.execute(
            text("""
                INSERT INTO app.users (id, email)
                SELECT id, lower(email) FROM auth.users WHERE lower(email) = lower(:e)
                ON CONFLICT DO NOTHING
            """),
            {"e": email},
        )
    return conn.execute(
        text("SELECT id FROM app.users WHERE lower(email) = lower(:e)"), {"e": email}
    ).scalar()


def _repoint(conn: Connection, tenant_id: UUID, old: UUID, new: UUID) -> None:
    """Moves everything that refers to the demo team member `old` over to the real person `new`
    (who becomes a member of the business first, so composite keys hold), then removes the demo
    profile."""
    conn.execute(
        text("""
            INSERT INTO app.tenant_members (tenant_id, user_id, role, location_ids,
                                            home_location_id, job_title)
            SELECT tenant_id, :new, role, location_ids, home_location_id, job_title
            FROM app.tenant_members WHERE tenant_id = :t AND user_id = :old
        """),
        {"t": tenant_id, "old": old, "new": new},
    )
    references = conn.execute(
        text("""
            SELECT DISTINCT c.conrelid::regclass::text, a.attname
            FROM pg_constraint c
            JOIN LATERAL unnest(c.conkey, c.confkey) AS k(col, ref) ON true
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.col
            JOIN pg_attribute r ON r.attrelid = c.confrelid AND r.attnum = k.ref
            WHERE c.contype = 'f' AND r.attname IN ('id', 'user_id')
              AND ((c.confrelid = 'app.users'::regclass AND r.attname = 'id')
                   OR (c.confrelid = 'app.tenant_members'::regclass AND r.attname = 'user_id'))
              AND c.conrelid <> 'app.tenant_members'::regclass
        """)
    ).all()
    for table, column in references:
        conn.execute(
            text(f"UPDATE {table} SET {column} = :new WHERE {column} = :old"),
            {"old": old, "new": new},
        )
    conn.execute(
        text("DELETE FROM app.tenant_members WHERE tenant_id = :t AND user_id = :old"),
        {"t": tenant_id, "old": old},
    )
    conn.execute(text("DELETE FROM app.users WHERE id = :old"), {"old": old})


def link_team_logins(conn: Connection, owner_email: str, tenants: dict[str, UUID]) -> dict:
    """Gives each plus address the demo team member it should be."""
    linked, skipped = [], []
    for tag, (business, branch_name, role, name, title) in TEAM_LOGINS.items():
        email = plus_address(owner_email, tag)
        user = _user(conn, email)
        tenant_id = tenants.get(business)
        if user is None or tenant_id is None:
            skipped.append(email)
            continue
        branch = _branch(conn, tenant_id, branch_name) if branch_name else None
        existing = conn.execute(
            text("SELECT role FROM app.tenant_members WHERE tenant_id = :t AND user_id = :u"),
            {"t": tenant_id, "u": user},
        ).scalar()
        if existing is None:
            demo = conn.execute(
                text("""
                    SELECT m.user_id FROM app.tenant_members m
                    JOIN app.users u ON u.id = m.user_id
                    WHERE m.tenant_id = :t AND m.role = 'staff'
                      AND u.email LIKE 'demo-coach-%@example.invalid'
                      AND (CAST(:b AS uuid) IS NULL OR m.location_ids @> ARRAY[CAST(:b AS uuid)]
                           OR m.home_location_id = :b)
                    ORDER BY m.created_at, m.user_id LIMIT 1
                """),
                {"t": tenant_id, "b": branch},
            ).scalar()
            if demo is not None:
                _repoint(conn, tenant_id, demo, user)
            else:
                conn.execute(
                    text("""
                        INSERT INTO app.tenant_members (tenant_id, user_id, role)
                        VALUES (:t, :u, 'staff')
                    """),
                    {"t": tenant_id, "u": user},
                )
        elif existing == "owner":
            skipped.append(email)
            continue
        conn.execute(
            text("""
                UPDATE app.tenant_members SET role = :role, location_ids = :branches,
                    home_location_id = :home, job_title = :title
                WHERE tenant_id = :t AND user_id = :u
            """),
            {
                "role": role,
                "branches": [branch] if branch and role != "manager" else [],
                "home": branch,
                "title": title,
                "t": tenant_id,
                "u": user,
            },
        )
        conn.execute(
            text(
                "UPDATE app.users SET full_name = :n WHERE id = :u AND coalesce(full_name, '') = ''"
            ),
            {"n": name, "u": user},
        )
        linked.append(email)
    return {"linked": linked, "skipped": skipped}


def _client_of(conn: Connection, tenant_id: UUID, user: UUID, branch: UUID | None) -> UUID:
    """The person's client record in the business (created from their profile)."""
    found = conn.execute(
        text("SELECT id FROM app.clients WHERE tenant_id = :t AND user_id = :u"),
        {"t": tenant_id, "u": user},
    ).scalar()
    if found:
        return found
    return conn.execute(
        text("""
            INSERT INTO app.clients (tenant_id, user_id, first_name, last_name, email, status,
                                     source, home_location_id)
            SELECT :t, u.id, coalesce(nullif(split_part(u.full_name, ' ', 1), ''),
                            split_part(u.email, '@', 1)),
                   nullif(substr(u.full_name, length(split_part(u.full_name, ' ', 1)) + 2), ''),
                   u.email, 'active', 'referral', :b
            FROM app.users u WHERE u.id = :u
            RETURNING id
        """),
        {"t": tenant_id, "u": user, "b": branch},
    ).scalar_one()


def _friend_code(conn: Connection, tenant_id: UUID, client: UUID) -> None:
    conn.execute(
        text("""
            INSERT INTO app.client_social (tenant_id, client_id, friend_code)
            VALUES (:t, :c, upper(substr(md5(CAST(:t AS text) || CAST(:c AS text)), 1, 10)))
            ON CONFLICT DO NOTHING
        """),
        {"t": tenant_id, "c": client},
    )


def _befriend(conn: Connection, tenant_id: UUID, a: UUID, b: UUID, status: str) -> None:
    for client in (a, b):
        _friend_code(conn, tenant_id, client)
    conn.execute(
        text("""
            INSERT INTO app.client_friendships
                (tenant_id, requester_id, addressee_id, status, responded_at)
            VALUES (:t, :a, :b, :status, CASE WHEN :status = 'accepted' THEN now() END)
            ON CONFLICT DO NOTHING
        """),
        {"t": tenant_id, "a": a, "b": b, "status": status},
    )


def _session(
    conn: Connection, tenant_id: UUID, branch: UUID, earliest: timedelta, skip: tuple = (),
    seats: int = 1,
) -> tuple[UUID, int] | None:  # fmt: skip
    """The first scheduled session after `earliest` from now with room for `seats` more people,
    at the branch if it has one, else at another branch of the business."""
    return conn.execute(
        text("""
            SELECT s.id, s.capacity FROM app.sessions s
            WHERE s.tenant_id = :t AND s.status = 'scheduled'
              AND s.starts_at > now() + :earliest AND s.id <> ALL(:skip)
              AND s.capacity - (SELECT count(*) FROM app.bookings b WHERE b.session_id = s.id
                                AND b.status IN ('booked', 'checked_in', 'no_show')) >= :seats
            ORDER BY (s.location_id = :l) DESC, s.starts_at LIMIT 1
        """),
        {"t": tenant_id, "l": branch, "earliest": earliest, "skip": list(skip), "seats": seats},
    ).first()


def _book(
    conn: Connection, tenant_id: UUID, session: UUID, client: UUID, entitlement: UUID | None
) -> None:
    conn.execute(
        text("""
            INSERT INTO app.bookings (tenant_id, session_id, client_id, entitlement_id, status)
            SELECT :t, :s, :c, :e, 'booked'
            WHERE NOT EXISTS (SELECT 1 FROM app.bookings WHERE session_id = :s AND client_id = :c)
        """),
        {"t": tenant_id, "s": session, "c": client, "e": entitlement},
    )


def _entitlement(conn: Connection, tenant_id: UUID, client: UUID, branch: UUID, kind: str,
                 ends_in_days: int, credits: int | None) -> UUID | None:  # fmt: skip
    """One of the business's plans of this kind, sold to the client and ending in a while."""
    if (found := conn.execute(
        text("SELECT id FROM app.entitlements WHERE tenant_id = :t AND client_id = :c LIMIT 1"),
        {"t": tenant_id, "c": client},
    ).scalar()):  # fmt: skip
        return found
    plan = conn.execute(
        text("""
            SELECT id, name, kind, credits, price_amount FROM app.plans
            WHERE tenant_id = :t AND kind = :k AND (:k <> 'punch_card' OR credits >= 3)
            ORDER BY price_amount LIMIT 1
        """),
        {"t": tenant_id, "k": kind},
    ).first()
    if plan is None:
        return None
    return conn.execute(
        text("""
            INSERT INTO app.entitlements
                (tenant_id, client_id, plan_id, name, kind, credits, starts_on, ends_on,
                 price_amount, price_currency, location_id)
            VALUES (:t, :c, :p, :name, :kind, :credits, current_date - 18,
                    current_date + :days, :price, 'ILS', :b)
            RETURNING id
        """),
        {
            "t": tenant_id, "c": client, "p": plan[0], "name": plan[1], "kind": plan[2],
            "credits": credits if credits is not None else plan[3], "days": ends_in_days,
            "price": plan[4], "b": branch,
        },
    ).scalar_one()  # fmt: skip


def seed_test_customer(conn: Connection, owner_email: str, customer_email: str,
                       tenants: dict[str, UUID]) -> dict:  # fmt: skip
    """The test customer and their friend as clients, with a believable week ahead."""
    customer = _user(conn, customer_email)
    friend = _user(conn, plus_address(owner_email, FRIEND_TAG))
    result = {"customer": customer is not None, "friend": friend is not None, "bookings": 0}
    if customer is None:
        return result
    mine: dict[str, UUID] = {}
    for business, branch_name in CUSTOMER_HOMES:
        tenant_id = tenants.get(business)
        branch = _branch(conn, tenant_id, branch_name) if tenant_id else None
        if branch is None:
            continue
        mine[business] = _client_of(conn, tenant_id, customer, branch)
    theirs: dict[str, UUID] = {}
    if friend is not None:
        for business, branch_name in FRIEND_HOMES:
            tenant_id = tenants.get(business)
            branch = _branch(conn, tenant_id, branch_name) if tenant_id else None
            if branch is not None:
                theirs[business] = _client_of(conn, tenant_id, friend, branch)

    gym = tenants.get(GYM)
    gym_branch = _branch(conn, gym, TA_STRENGTH) if gym else None
    if gym and gym_branch and GYM in mine:
        me = mine[GYM]
        # A membership that ends in 12 days, and no health declaration yet (the form is due).
        membership = _entitlement(conn, gym, me, gym_branch, "membership", 12, None)
        conn.execute(
            text("DELETE FROM app.health_declarations WHERE tenant_id = :t AND client_id = :c"),
            {"t": gym, "c": me},
        )
        friends = [theirs[GYM]] if GYM in theirs else []
        # Four more gym members are friends with them.
        for other in conn.execute(
            text("""
                SELECT c.id FROM app.clients c JOIN app.users u ON u.id = c.user_id
                WHERE c.tenant_id = :t AND c.id <> :me
                  AND u.email LIKE 'demo-client-%@example.invalid'
                ORDER BY c.created_at, c.id LIMIT 4
            """),
            {"t": gym, "me": me},
        ).scalars():
            friends.append(other)
        for other in friends:
            _befriend(conn, gym, me, other, "accepted")
        pending = conn.execute(
            text("""
                SELECT c.id FROM app.clients c JOIN app.users u ON u.id = c.user_id
                WHERE c.tenant_id = :t AND c.id <> ALL(:known)
                  AND u.email LIKE 'demo-client-%@example.invalid'
                ORDER BY c.created_at, c.id LIMIT 1
            """),
            {"t": gym, "known": [me, *friends]},
        ).scalar()
        if pending:
            _befriend(conn, gym, pending, me, "pending")
        # A class tomorrow with two friends in it; a one-on-one slot when there are no classes.
        tomorrow = _session(conn, gym, gym_branch, timedelta(hours=14), seats=3) or _session(
            conn, gym, gym_branch, timedelta(hours=14)
        )
        if tomorrow:
            _book(conn, gym, tomorrow[0], me, membership)
            result["bookings"] += 1
            if tomorrow[1] >= 3:
                for other in friends[:2]:
                    _book(conn, gym, tomorrow[0], other, None)
                result["bookings"] += 2
        later = _session(conn, gym, gym_branch, timedelta(days=3),
                         skip=(tomorrow[0],) if tomorrow else ())  # fmt: skip
        if later and friends:
            conn.execute(
                text("""
                    INSERT INTO app.class_invites
                        (tenant_id, session_id, inviter_id, invitee_id, expires_at)
                    SELECT :t, :s, :a, :b, now() + interval '2 days'
                    WHERE NOT EXISTS (SELECT 1 FROM app.class_invites
                                      WHERE session_id = :s AND invitee_id = :b)
                """),
                {"t": gym, "s": later[0], "a": friends[0], "b": me},
            )

    tennis = tenants.get(TENNIS)  # courts are rented by the hour (reservations), not sessions
    tennis_branch = _branch(conn, tennis, HERZLIYA) if tennis else None
    if tennis and tennis_branch and TENNIS in mine:
        _entitlement(conn, tennis, mine[TENNIS], tennis_branch, "punch_card", 60, 3)
        if TENNIS in theirs:
            _befriend(conn, tennis, mine[TENNIS], theirs[TENNIS], "accepted")

    barber = tenants.get(BARBER)
    barber_branch = _branch(conn, barber, FLORENTIN) if barber else None
    if barber and barber_branch and BARBER in mine:
        loyalty = _entitlement(conn, barber, mine[BARBER], barber_branch, "punch_card", 120, 10)
        cut = _session(conn, barber, barber_branch, timedelta(days=2))
        if cut:
            _book(conn, barber, cut[0], mine[BARBER], loyalty)
            result["bookings"] += 1
    return result


def seed_shared_people(conn: Connection, tenants: dict[str, UUID]) -> dict[str, int]:
    """People who are clients of several businesses at once (one profile, a record in each)."""
    gym = tenants.get(GYM)
    if gym is None:
        return {"shared": 0}
    people = conn.execute(
        text("""
            SELECT u.id FROM app.clients c JOIN app.users u ON u.id = c.user_id
            WHERE c.tenant_id = :t AND u.email LIKE 'demo-client-%@example.invalid'
            ORDER BY c.created_at DESC, c.id LIMIT :n
        """),
        {"t": gym, "n": SHARED_PEOPLE},
    ).scalars().all()  # fmt: skip
    added = 0
    for index, user in enumerate(people):
        for business, limit, branch_name in (
            (TENNIS, SHARED_PEOPLE, HERZLIYA),
            (BARBER, SHARED_BARBER, FLORENTIN),
            (CLINIC, SHARED_CLINIC, PETAH_TIKVA),
        ):
            tenant_id = tenants.get(business)
            if tenant_id is None or index >= limit:
                continue
            branch = _branch(conn, tenant_id, branch_name)
            before = conn.execute(
                text("SELECT count(*) FROM app.clients WHERE tenant_id = :t"), {"t": tenant_id}
            ).scalar_one()
            _client_of(conn, tenant_id, user, branch)
            added += (
                conn.execute(
                    text("SELECT count(*) FROM app.clients WHERE tenant_id = :t"), {"t": tenant_id}
                ).scalar_one()
                - before
            )
    return {"shared": len(people), "records_added": added}


def seed_social(
    conn: Connection, owner_email: str, customer_email: str = CUSTOMER_EMAIL
) -> dict[str, object]:
    refuse_blocked_owner(owner_email)
    owner = conn.execute(
        text("SELECT id FROM app.users WHERE lower(email) = lower(:e)"), {"e": owner_email}
    ).scalar()
    tenants = _tenants(conn, owner)
    return {
        "logins": link_team_logins(conn, owner_email, tenants),
        "shared": seed_shared_people(conn, tenants),
        "test_customer": seed_test_customer(conn, owner_email, customer_email, tenants),
    }
