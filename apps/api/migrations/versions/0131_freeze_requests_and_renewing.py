"""Renewing memberships and freeze requests from the app (round 7, R23).

Expand step. Plans and the entitlements sold from them gain a billing cycle and "renews
automatically" (with the next billing date); a business gets freeze rules (`tenant_freeze_rules`:
requests on or off, shortest and longest freeze, a yearly bank of days, notice, a fee, whether a
freeze defers the next charge or credits it, and reasons approved automatically); clients ask for
a freeze (`freeze_requests`) and a manager decides. Two functions apply a freeze and end one early
so the dates, the next billing date and the credit are always changed together, for a manager and
for a client whose request is approved automatically.

Nothing existing changes: a plan with no cycle behaves as before, a business with no rules row
does not accept requests, and the previous release never selects the new columns.

Revision ID: 0131
Revises: 0130
Create Date: 2026-10-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0131"
down_revision: str | None = "0130"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOTIFICATION_KINDS = (
    "waitlist_promoted",
    "booked_by_studio",
    "booking_cancelled_by_studio",
    "session_cancelled",
    "session_moved",
    "health_approved",
    "health_rejected",
    "session_reminder",
    "plan_ending",
    "friend_request",
    "class_invite",
)
NEW_KINDS = ("freeze_approved", "freeze_rejected")


def _kinds_check(kinds: tuple[str, ...]) -> None:
    listed = ", ".join(f"'{kind}'" for kind in kinds)
    op.execute("ALTER TABLE app.notifications DROP CONSTRAINT notifications_kind_check")
    op.execute(
        "ALTER TABLE app.notifications ADD CONSTRAINT notifications_kind_check "
        f"CHECK (kind IN ({listed}))"
    )


# What a freeze of these days would do to this entitlement. Used for the preview the client sees
# before sending and by apply_freeze, so the two can never disagree. The cycle length is the real
# length of the cycle that ends on the next billing date (a month has 28 to 31 days).
FREEZE_EFFECT = """
    CREATE FUNCTION app.freeze_effect(p_entitlement_id uuid, p_starts date, p_ends date)
    RETURNS TABLE (
        days integer, new_ends_on date, billing_mode text, billing_shift_days integer,
        next_billing_from date, next_billing_to date, cycle_days integer,
        credit_amount integer, fee_amount integer
    )
    LANGUAGE sql STABLE SET search_path = ''
    AS $$
        WITH e AS (
            SELECT x.*, (p_ends - p_starts + 1) AS span,
                   coalesce((SELECT r.billing_mode FROM app.tenant_freeze_rules r
                             WHERE r.tenant_id = x.tenant_id), 'defer') AS rule_mode,
                   coalesce((SELECT r.fee_amount FROM app.tenant_freeze_rules r
                             WHERE r.tenant_id = x.tenant_id), 0) AS rule_fee,
                   CASE WHEN x.auto_renew AND x.next_billing_on IS NOT NULL THEN
                       CASE x.billing_cycle
                           WHEN 'custom' THEN x.billing_cycle_days
                           ELSE x.next_billing_on - (x.next_billing_on - CASE x.billing_cycle
                               WHEN 'monthly' THEN interval '1 month'
                               WHEN 'quarterly' THEN interval '3 months'
                               ELSE interval '1 year' END)::date
                       END
                   END AS cycle
            FROM app.entitlements x WHERE x.id = p_entitlement_id
        ), m AS (
            SELECT e.*, CASE
                WHEN e.cycle IS NULL THEN 'none'
                WHEN e.rule_mode = 'credit' THEN 'credit'
                WHEN e.next_billing_on >= p_starts THEN 'defer'
                ELSE 'none' END AS mode
            FROM e
        )
        SELECT m.span, m.ends_on + m.span, m.mode,
               CASE WHEN m.mode = 'defer' THEN m.span ELSE 0 END,
               m.next_billing_on,
               CASE WHEN m.mode = 'defer' THEN m.next_billing_on + m.span
                    ELSE m.next_billing_on END,
               m.cycle,
               CASE WHEN m.mode = 'credit'
                    THEN least(m.price_amount,
                               ((m.price_amount::bigint * m.span + m.cycle - 1) / m.cycle)::integer)
                    ELSE 0 END,
               m.rule_fee
        FROM m
    $$
"""

# Creates the freeze and changes the entitlement. A manager may freeze any entitlement of their
# business; a client only by way of their own pending request (approved automatically).
APPLY_FREEZE = """
    CREATE FUNCTION app.apply_freeze(
        p_entitlement_id uuid, p_starts date, p_ends date, p_reason text,
        p_request_id uuid, p_charge_fee boolean, p_auto boolean, p_note text
    ) RETURNS uuid
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
    AS $$
    DECLARE
        v_e app.entitlements;
        v_req app.freeze_requests;
        fx record;
        v_fee integer;
        v_freeze uuid;
    BEGIN
        SELECT * INTO v_e FROM app.entitlements WHERE id = p_entitlement_id FOR UPDATE;
        IF v_e.id IS NULL THEN
            RAISE EXCEPTION 'entitlement not found' USING ERRCODE = 'P0002';
        END IF;
        IF p_request_id IS NOT NULL THEN
            SELECT * INTO v_req FROM app.freeze_requests WHERE id = p_request_id FOR UPDATE;
            IF v_req.id IS NULL OR v_req.entitlement_id <> v_e.id OR v_req.status <> 'pending' THEN
                RAISE EXCEPTION 'request not found' USING ERRCODE = 'P0002';
            END IF;
        END IF;
        IF (v_e.tenant_id = app.current_tenant_id()
            OR (p_request_id IS NOT NULL AND p_auto
                AND v_e.client_id = app.current_client_id()
                AND v_req.client_id = v_e.client_id)) IS NOT TRUE THEN
            RAISE EXCEPTION 'not allowed' USING ERRCODE = 'P0002';
        END IF;

        SELECT * INTO fx FROM app.freeze_effect(p_entitlement_id, p_starts, p_ends);
        v_fee := CASE WHEN p_charge_fee THEN fx.fee_amount ELSE 0 END;
        INSERT INTO app.entitlement_freezes
            (tenant_id, entitlement_id, starts_on, ends_on, reason, created_by, request_id,
             billing_mode, billing_shift_days, credit_amount, fee_amount, cycle_days)
        VALUES (v_e.tenant_id, v_e.id, p_starts, p_ends, p_reason,
                CASE WHEN p_auto THEN NULL ELSE app.current_user_id() END, p_request_id,
                fx.billing_mode, fx.billing_shift_days, fx.credit_amount, v_fee, fx.cycle_days)
        RETURNING id INTO v_freeze;
        UPDATE app.entitlements
        SET ends_on = ends_on + fx.days,
            next_billing_on = CASE WHEN fx.billing_mode = 'defer'
                                   THEN next_billing_on + fx.days ELSE next_billing_on END,
            billing_adjustment = billing_adjustment + fx.credit_amount - v_fee,
            updated_at = now()
        WHERE id = v_e.id;
        IF p_request_id IS NOT NULL THEN
            UPDATE app.freeze_requests
            SET status = 'approved', approved_starts_on = p_starts, approved_ends_on = p_ends,
                decided_by = CASE WHEN p_auto THEN NULL ELSE app.current_user_id() END,
                decided_at = now(), decision_note = p_note, auto_approved = p_auto
            WHERE id = p_request_id;
        END IF;
        RETURN v_freeze;
    END
    $$
"""

# "I'm back early": the freeze ends the day before today (or disappears when it has not begun),
# the end date comes back by the unused days, and so do the deferred charge and the credit.
END_FREEZE_EARLY = """
    CREATE FUNCTION app.end_freeze_early(p_freeze_id uuid) RETURNS void
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
    AS $$
    DECLARE
        f app.entitlement_freezes;
        v_e app.entitlements;
        v_today date;
        v_last date;
        v_unused integer;
        v_days integer;
        v_credit integer;
    BEGIN
        SELECT * INTO f FROM app.entitlement_freezes WHERE id = p_freeze_id FOR UPDATE;
        IF f.id IS NULL THEN
            RAISE EXCEPTION 'freeze not found' USING ERRCODE = 'P0002';
        END IF;
        SELECT * INTO v_e FROM app.entitlements WHERE id = f.entitlement_id FOR UPDATE;
        IF (v_e.tenant_id = app.current_tenant_id()
            OR v_e.client_id = app.current_client_id()) IS NOT TRUE THEN
            RAISE EXCEPTION 'not allowed' USING ERRCODE = 'P0002';
        END IF;
        SELECT (now() AT TIME ZONE t.time_zone)::date INTO v_today
        FROM app.tenants t WHERE t.id = v_e.tenant_id;
        IF f.ends_on < v_today THEN
            RAISE EXCEPTION 'freeze is over' USING ERRCODE = 'P0001';
        END IF;

        v_last := v_today - 1;
        IF v_last < f.starts_on THEN  -- not begun: undo it completely, fee included
            UPDATE app.entitlements
            SET ends_on = ends_on - (f.ends_on - f.starts_on + 1),
                next_billing_on = next_billing_on - f.billing_shift_days,
                billing_adjustment = billing_adjustment - f.credit_amount + f.fee_amount,
                updated_at = now()
            WHERE id = v_e.id;
            DELETE FROM app.entitlement_freezes WHERE id = f.id;
            RETURN;
        END IF;

        v_unused := f.ends_on - v_last;
        v_days := v_last - f.starts_on + 1;
        v_credit := CASE WHEN f.billing_mode = 'credit'
            THEN least(v_e.price_amount,
                       ((v_e.price_amount::bigint * v_days + f.cycle_days - 1)
                        / f.cycle_days)::integer)
            ELSE 0 END;
        UPDATE app.entitlements
        SET ends_on = ends_on - v_unused,
            next_billing_on = next_billing_on - least(v_unused, f.billing_shift_days),
            billing_adjustment = billing_adjustment - (f.credit_amount - v_credit),
            updated_at = now()
        WHERE id = v_e.id;
        UPDATE app.entitlement_freezes
        SET ends_on = v_last,
            billing_shift_days = billing_shift_days - least(v_unused, billing_shift_days),
            credit_amount = v_credit
        WHERE id = f.id;
    END
    $$
"""


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.plans
            ADD COLUMN billing_cycle text
                CONSTRAINT plans_billing_cycle_check
                CHECK (billing_cycle IN ('monthly', 'quarterly', 'yearly', 'custom')),
            ADD COLUMN billing_cycle_days integer
                CONSTRAINT plans_billing_cycle_days_check
                CHECK (billing_cycle_days BETWEEN 1 AND 1095),
            ADD COLUMN auto_renew boolean NOT NULL DEFAULT false,
            ADD CONSTRAINT plans_billing_cycle_shape CHECK (
                (billing_cycle IS NULL AND billing_cycle_days IS NULL AND NOT auto_renew)
                OR (billing_cycle IS NOT NULL AND kind = 'membership'
                    AND (billing_cycle = 'custom') = (billing_cycle_days IS NOT NULL))
            )
    """)
    op.execute("""
        ALTER TABLE app.entitlements
            ADD COLUMN billing_cycle text
                CONSTRAINT entitlements_billing_cycle_check
                CHECK (billing_cycle IN ('monthly', 'quarterly', 'yearly', 'custom')),
            ADD COLUMN billing_cycle_days integer
                CONSTRAINT entitlements_billing_cycle_days_check
                CHECK (billing_cycle_days BETWEEN 1 AND 1095),
            ADD COLUMN auto_renew boolean NOT NULL DEFAULT false,
            ADD COLUMN next_billing_on date,
            ADD COLUMN billing_adjustment integer NOT NULL DEFAULT 0
    """)
    op.execute("""
        ALTER TABLE app.entitlement_freezes
            ADD COLUMN request_id uuid,
            ADD COLUMN billing_mode text NOT NULL DEFAULT 'none'
                CONSTRAINT entitlement_freezes_billing_mode_check
                CHECK (billing_mode IN ('none', 'defer', 'credit')),
            ADD COLUMN billing_shift_days integer NOT NULL DEFAULT 0
                CONSTRAINT entitlement_freezes_shift_check CHECK (billing_shift_days >= 0),
            ADD COLUMN credit_amount integer NOT NULL DEFAULT 0
                CONSTRAINT entitlement_freezes_credit_check CHECK (credit_amount >= 0),
            ADD COLUMN fee_amount integer NOT NULL DEFAULT 0
                CONSTRAINT entitlement_freezes_fee_check CHECK (fee_amount >= 0),
            ADD COLUMN cycle_days integer
    """)

    op.execute("""
        CREATE TABLE app.tenant_freeze_rules (
            tenant_id             uuid PRIMARY KEY REFERENCES app.tenants (id) ON DELETE CASCADE,
            allow_requests        boolean NOT NULL DEFAULT false,
            min_days              integer NOT NULL DEFAULT 1 CHECK (min_days BETWEEN 1 AND 90),
            max_days              integer NOT NULL DEFAULT 30 CHECK (max_days BETWEEN 1 AND 90),
            yearly_bank_days      integer CHECK (yearly_bank_days BETWEEN 1 AND 366),
            notice_days           integer NOT NULL DEFAULT 0 CHECK (notice_days BETWEEN 0 AND 60),
            fee_amount            integer NOT NULL DEFAULT 0 CHECK (fee_amount >= 0),
            billing_mode          text NOT NULL DEFAULT 'defer'
                                  CHECK (billing_mode IN ('defer', 'credit')),
            auto_approve_reasons  text[] NOT NULL DEFAULT '{}',
            updated_at            timestamptz NOT NULL DEFAULT now(),
            CHECK (max_days >= min_days),
            CHECK (auto_approve_reasons <@ ARRAY['travel', 'reserve_duty', 'illness',
                                                 'pregnancy', 'other']::text[])
        )
    """)
    op.execute("""
        CREATE TABLE app.freeze_requests (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id         uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            client_id         uuid NOT NULL,
            entitlement_id    uuid NOT NULL,
            starts_on         date NOT NULL,
            ends_on           date NOT NULL,
            reason            text NOT NULL
                              CHECK (reason IN ('travel', 'reserve_duty', 'illness',
                                                'pregnancy', 'other')),
            note              text CHECK (char_length(note) <= 500),
            status            text NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
            approved_starts_on date,
            approved_ends_on  date,
            auto_approved     boolean NOT NULL DEFAULT false,
            decided_by        uuid REFERENCES app.users (id) ON DELETE SET NULL,
            decided_at        timestamptz,
            decision_note     text CHECK (char_length(decision_note) <= 500),
            created_at        timestamptz NOT NULL DEFAULT now(),
            CHECK (ends_on >= starts_on AND ends_on - starts_on <= 365),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, entitlement_id) REFERENCES app.entitlements (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX freeze_requests_tenant_idx ON app.freeze_requests"
        " (tenant_id, status, starts_on)"
    )
    op.execute(
        "CREATE INDEX freeze_requests_client_idx ON app.freeze_requests"
        " (tenant_id, client_id, created_at)"
    )
    op.execute(
        "CREATE INDEX freeze_requests_entitlement_idx ON app.freeze_requests"
        " (tenant_id, entitlement_id, status)"
    )
    op.execute(
        "CREATE INDEX entitlement_freezes_request_idx ON app.entitlement_freezes (request_id)"
    )
    op.execute("""
        ALTER TABLE app.entitlement_freezes
            ADD CONSTRAINT entitlement_freezes_request_fkey
            FOREIGN KEY (request_id) REFERENCES app.freeze_requests (id) ON DELETE SET NULL
    """)

    for table in ("tenant_freeze_rules", "freeze_requests"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE ON app.{table} TO app_api")
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)
    # A client reads the business's freeze rules, and sends, reads and withdraws their own requests.
    op.execute("""
        CREATE POLICY tenant_freeze_rules_client_select ON app.tenant_freeze_rules
        FOR SELECT TO app_api USING (tenant_id = app.client_tenant_id())
    """)
    op.execute("""
        CREATE POLICY freeze_requests_client_select ON app.freeze_requests
        FOR SELECT TO app_api USING (client_id = app.current_client_id())
    """)
    op.execute("""
        CREATE POLICY freeze_requests_client_insert ON app.freeze_requests
        FOR INSERT TO app_api
        WITH CHECK (tenant_id = app.client_tenant_id() AND client_id = app.current_client_id()
                    AND status = 'pending')
    """)
    op.execute("""
        CREATE POLICY freeze_requests_client_cancel ON app.freeze_requests
        FOR UPDATE TO app_api
        USING (client_id = app.current_client_id() AND status = 'pending')
        WITH CHECK (client_id = app.current_client_id() AND status = 'cancelled')
    """)

    op.execute(FREEZE_EFFECT)
    op.execute(APPLY_FREEZE)
    op.execute(END_FREEZE_EARLY)
    for signature in (
        "freeze_effect(uuid, date, date)",
        "apply_freeze(uuid, date, date, text, uuid, boolean, boolean, text)",
        "end_freeze_early(uuid)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION app.{signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION app.{signature} TO app_api")

    _kinds_check((*NOTIFICATION_KINDS, *NEW_KINDS))


def downgrade() -> None:
    # contract: only the downgrade removes the freeze functions, tables and columns, which no
    # earlier release reads or calls.
    op.execute("DELETE FROM app.notifications WHERE kind IN ('freeze_approved', 'freeze_rejected')")
    _kinds_check(NOTIFICATION_KINDS)
    op.execute("DROP FUNCTION app.end_freeze_early(uuid)")
    op.execute(
        "DROP FUNCTION app.apply_freeze(uuid, date, date, text, uuid, boolean, boolean, text)"
    )
    op.execute("DROP FUNCTION app.freeze_effect(uuid, date, date)")
    op.execute(
        "ALTER TABLE app.entitlement_freezes DROP CONSTRAINT entitlement_freezes_request_fkey"
    )
    op.execute("DROP TABLE app.freeze_requests, app.tenant_freeze_rules")
    op.execute("""
        ALTER TABLE app.entitlement_freezes
            DROP COLUMN cycle_days, DROP COLUMN fee_amount, DROP COLUMN credit_amount,
            DROP COLUMN billing_shift_days, DROP COLUMN billing_mode, DROP COLUMN request_id
    """)
    op.execute("""
        ALTER TABLE app.entitlements
            DROP COLUMN billing_adjustment, DROP COLUMN next_billing_on, DROP COLUMN auto_renew,
            DROP COLUMN billing_cycle_days, DROP COLUMN billing_cycle
    """)
    op.execute("""
        ALTER TABLE app.plans
            DROP CONSTRAINT plans_billing_cycle_shape,
            DROP COLUMN auto_renew, DROP COLUMN billing_cycle_days, DROP COLUMN billing_cycle
    """)
