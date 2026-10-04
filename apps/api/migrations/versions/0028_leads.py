"""CRM: leads (people interested in the business who are not clients yet) and their activity.

A lead moves through stages (new → contacted → trial → offer → won / lost). Winning a lead
links it to a client record. People can also leave their details on the business's public
inquiry form (by join code); that goes through app.submit_lead, rate-limited, and only works
when the business has the CRM module.

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAGES = "'new', 'contacted', 'trial', 'offer', 'won', 'lost'"


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE app.leads (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id      uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            first_name     text NOT NULL CHECK (length(first_name) BETWEEN 1 AND 100),
            last_name      text CHECK (length(last_name) <= 100),
            email          text CHECK (length(email) <= 254),
            phone          text CHECK (length(phone) <= 30),
            interest       text CHECK (length(interest) <= 2000),
            source         text NOT NULL DEFAULT 'manual' CHECK (source IN (
                'manual', 'form', 'walk_in', 'referral', 'instagram', 'facebook', 'google',
                'website', 'other')),
            campaign       text CHECK (length(campaign) <= 100),
            stage          text NOT NULL DEFAULT 'new' CHECK (stage IN ({STAGES})),
            lost_reason    text CHECK (length(lost_reason) <= 500),
            follow_up_on   date,
            owner_user_id  uuid,
            client_id      uuid,
            created_at     timestamptz NOT NULL DEFAULT now(),
            updated_at     timestamptz NOT NULL DEFAULT now(),
            stage_changed_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, client_id) REFERENCES app.clients (tenant_id, id)
                ON DELETE SET NULL (client_id),
            FOREIGN KEY (tenant_id, owner_user_id)
                REFERENCES app.tenant_members (tenant_id, user_id)
                ON DELETE SET NULL (owner_user_id)
        )
    """)
    op.execute("CREATE INDEX leads_stage ON app.leads (tenant_id, stage, created_at)")
    op.execute("CREATE INDEX leads_client ON app.leads (client_id)")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app.leads TO app_api")
    op.execute("ALTER TABLE app.leads ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY leads_tenant ON app.leads TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)

    op.execute(f"""
        CREATE TABLE app.lead_activities (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id     uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            lead_id       uuid NOT NULL,
            kind          text NOT NULL CHECK (kind IN (
                'note', 'call', 'message', 'meeting', 'stage', 'created', 'converted')),
            note          text CHECK (length(note) <= 2000),
            to_stage      text CHECK (to_stage IN ({STAGES})),
            actor_user_id uuid,
            occurred_at   timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, lead_id) REFERENCES app.leads (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX lead_activities_lead ON app.lead_activities (lead_id, occurred_at)")
    op.execute("GRANT SELECT, INSERT ON app.lead_activities TO app_api")
    op.execute("ALTER TABLE app.lead_activities ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY lead_activities_tenant ON app.lead_activities TO app_api
        USING (tenant_id = app.current_tenant_id())
        WITH CHECK (tenant_id = app.current_tenant_id())
    """)

    # The public inquiry form: anyone with the business's join code, CRM module on, at most
    # 3 inquiries per email or phone an hour per business.
    op.execute("""
        CREATE FUNCTION app.submit_lead(
            p_code text, p_first_name text, p_last_name text, p_email text, p_phone text,
            p_interest text
        ) RETURNS uuid
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
        DECLARE
            v_tenant uuid;
            v_id uuid;
        BEGIN
            SELECT t.id INTO v_tenant FROM app.tenants t
            WHERE t.join_code = upper(trim(p_code))
              AND EXISTS (SELECT 1 FROM app.tenant_modules m
                          WHERE m.tenant_id = t.id AND m.module_key = 'crm');
            IF v_tenant IS NULL THEN
                RAISE EXCEPTION 'no such form' USING ERRCODE = 'P0002';
            END IF;
            IF (SELECT count(*) FROM app.leads l
                WHERE l.tenant_id = v_tenant AND l.source = 'form'
                  AND l.created_at > now() - interval '1 hour'
                  AND (lower(l.email) = lower(p_email) OR l.phone = p_phone)) >= 3 THEN
                RAISE EXCEPTION 'too many requests' USING ERRCODE = 'P0001';
            END IF;
            INSERT INTO app.leads (tenant_id, first_name, last_name, email, phone, interest, source)
            VALUES (v_tenant, p_first_name, p_last_name, lower(p_email), p_phone, p_interest,
                    'form')
            RETURNING id INTO v_id;
            INSERT INTO app.lead_activities (tenant_id, lead_id, kind, to_stage)
            VALUES (v_tenant, v_id, 'created', 'new');
            RETURN v_id;
        END
        $$
    """)
    signature = "app.submit_lead(text, text, text, text, text, text)"
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO app_api")

    # Whether the business's public inquiry form is open (before anyone signs in).
    op.execute("""
        CREATE FUNCTION app.accepts_inquiries(p_code text) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
            SELECT EXISTS (
                SELECT 1 FROM app.tenants t JOIN app.tenant_modules m ON m.tenant_id = t.id
                WHERE t.join_code = upper(trim(p_code)) AND m.module_key = 'crm'
            )
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION app.accepts_inquiries(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION app.accepts_inquiries(text) TO app_api")


def downgrade() -> None:
    op.execute("DROP FUNCTION app.accepts_inquiries(text)")
    op.execute("DROP FUNCTION app.submit_lead(text, text, text, text, text, text)")
    op.execute("DROP TABLE app.lead_activities")
    op.execute("DROP TABLE app.leads")
