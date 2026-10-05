"""Promo codes for plans bought in the client app: a percentage or a fixed amount off, for
every plan or one, optionally within dates and up to a number of uses.

Clients can't change checkouts, so a code is applied through app.apply_promo_code (SECURITY
DEFINER), which checks the code against the client's own pending checkout and re-prices it from
its list price. A use is counted when a checkout with the code is paid.

Revision ID: 0035
Revises: 0034
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.promo_codes (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id    uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            code         text NOT NULL CHECK (code ~ '^[A-Z0-9_-]{3,20}$'),
            percent_off  smallint CHECK (percent_off BETWEEN 1 AND 100),
            amount_off   integer CHECK (amount_off > 0),
            plan_id      uuid,
            starts_on    date,
            ends_on      date,
            max_uses     integer CHECK (max_uses > 0),
            active       boolean NOT NULL DEFAULT true,
            created_at   timestamptz NOT NULL DEFAULT now(),
            CHECK ((percent_off IS NULL) <> (amount_off IS NULL)),
            CHECK (ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on),
            UNIQUE (tenant_id, code),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, plan_id) REFERENCES app.plans (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE (active), DELETE ON app.promo_codes TO app_api")
    op.execute("ALTER TABLE app.promo_codes ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY promo_codes_tenant ON app.promo_codes TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)

    op.execute("ALTER TABLE app.checkouts ADD COLUMN list_amount integer")
    op.execute("UPDATE app.checkouts SET list_amount = amount")
    op.execute("ALTER TABLE app.checkouts ALTER COLUMN list_amount SET NOT NULL")
    op.execute("""
        ALTER TABLE app.checkouts
            ADD COLUMN discount integer NOT NULL DEFAULT 0 CHECK (discount >= 0),
            ADD COLUMN promo_code_id uuid,
            ADD FOREIGN KEY (tenant_id, promo_code_id) REFERENCES app.promo_codes (tenant_id, id)
                ON DELETE SET NULL (promo_code_id)
    """)
    # Clients see the codes on their own checkouts (to show what they applied).
    op.execute("""
        CREATE POLICY promo_codes_client_select ON app.promo_codes FOR SELECT TO app_api
        USING (EXISTS (SELECT 1 FROM app.checkouts k
                       WHERE k.promo_code_id = promo_codes.id
                         AND k.client_id = app.current_client_id()))
    """)

    # New checkouts start at the list price.
    op.execute("""
        CREATE FUNCTION app.checkout_list_amount() RETURNS trigger
        LANGUAGE plpgsql SET search_path = '' AS $$
        BEGIN
            NEW.list_amount := coalesce(NEW.list_amount, NEW.amount);
            RETURN NEW;
        END
        $$
    """)
    op.execute("""
        CREATE TRIGGER checkouts_list_amount BEFORE INSERT ON app.checkouts
        FOR EACH ROW EXECUTE FUNCTION app.checkout_list_amount()
    """)

    op.execute("""
        CREATE FUNCTION app.apply_promo_code(p_checkout uuid, p_code text) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v app.checkouts;
            v_code app.promo_codes;
            v_today date;
            v_discount integer;
        BEGIN
            SELECT * INTO v FROM app.checkouts WHERE id = p_checkout FOR UPDATE;
            IF v.id IS NULL OR v.client_id IS DISTINCT FROM app.current_client_id() THEN
                RAISE EXCEPTION 'checkout not found' USING ERRCODE = 'P0002';
            END IF;
            IF v.status <> 'pending' THEN
                RAISE EXCEPTION 'checkout is %', v.status USING ERRCODE = 'P0001';
            END IF;
            IF p_code IS NULL OR trim(p_code) = '' THEN  -- remove the code
                UPDATE app.checkouts SET amount = list_amount, discount = 0, promo_code_id = NULL
                WHERE id = v.id;
                RETURN;
            END IF;
            SELECT (now() AT TIME ZONE t.time_zone)::date INTO v_today
            FROM app.tenants t WHERE t.id = v.tenant_id;
            SELECT * INTO v_code FROM app.promo_codes c
            WHERE c.tenant_id = v.tenant_id AND c.code = upper(trim(p_code)) AND c.active
              AND (c.plan_id IS NULL OR c.plan_id = v.plan_id)
              AND (c.starts_on IS NULL OR c.starts_on <= v_today)
              AND (c.ends_on IS NULL OR c.ends_on >= v_today)
              AND (c.max_uses IS NULL OR c.max_uses > (
                  SELECT count(*) FROM app.checkouts k
                  WHERE k.promo_code_id = c.id AND k.status = 'paid'));
            IF v_code.id IS NULL THEN
                RAISE EXCEPTION 'invalid code' USING ERRCODE = '22023';
            END IF;
            v_discount := least(v.list_amount, coalesce(
                v_code.amount_off, round(v.list_amount * v_code.percent_off / 100.0)::integer));
            UPDATE app.checkouts
            SET amount = v.list_amount - v_discount, discount = v_discount,
                promo_code_id = v_code.id
            WHERE id = v.id;
        END
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.apply_promo_code(uuid, text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.apply_promo_code(uuid, text) TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.apply_promo_code(uuid, text)")
    op.execute("DROP TRIGGER checkouts_list_amount ON app.checkouts")
    op.execute("DROP FUNCTION app.checkout_list_amount()")
    op.execute("""
        ALTER TABLE app.checkouts
            DROP COLUMN promo_code_id, DROP COLUMN discount, DROP COLUMN list_amount
    """)
    op.execute("DROP TABLE app.promo_codes")
