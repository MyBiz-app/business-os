"""A payment webhook completes only a checkout of the business named in its address.

The webhook is verified with the secret of the business in the URL; without this check, a
business could sign a notification with its own secret and complete another business's
checkout (security review, #51).

Revision ID: 0054
Revises: 0053
Create Date: 2026-10-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0054"
down_revision: str | None = "0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BODY = """
    LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = ''
    AS $$
    DECLARE
        v app.checkouts;
    BEGIN
        -- Called after the API verified the provider's webhook signature: the checkout must
        -- be that business's and that provider's, for that amount.
        SELECT * INTO v FROM app.checkouts WHERE id = p_checkout_id;
        IF v.id IS NULL OR v.provider <> p_provider OR v.provider = 'simulated' {tenant_check}THEN
            RAISE EXCEPTION 'checkout not found' USING ERRCODE = 'P0002';
        END IF;
        IF v.amount <> p_amount OR v.currency <> p_currency THEN
            RAISE EXCEPTION 'amount does not match' USING ERRCODE = '22023';
        END IF;
        RETURN app.finish_checkout(v.id, p_ref);
    END
    $$
"""
OLD = "app.complete_provider_checkout(uuid, text, text, integer, text)"
NEW = "app.complete_provider_checkout(uuid, uuid, text, text, integer, text)"


def upgrade() -> None:
    op.execute(f"DROP FUNCTION {OLD}")
    op.execute(
        """
        CREATE FUNCTION app.complete_provider_checkout(
            p_tenant_id uuid, p_checkout_id uuid, p_provider text, p_ref text, p_amount integer,
            p_currency text
        ) RETURNS uuid
        """
        + BODY.replace("{tenant_check}", "\n           OR v.tenant_id <> p_tenant_id ")
    )
    op.execute(f"REVOKE ALL ON FUNCTION {NEW} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {NEW} TO app_api")


def downgrade() -> None:
    op.execute(f"DROP FUNCTION {NEW}")
    op.execute(
        """
        CREATE FUNCTION app.complete_provider_checkout(
            p_checkout_id uuid, p_provider text, p_ref text, p_amount integer, p_currency text
        ) RETURNS uuid
        """
        + BODY.replace("{tenant_check}", "")
    )
    op.execute(f"REVOKE ALL ON FUNCTION {OLD} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {OLD} TO app_api")
