"""Legal readiness of a business (round 6, K2).

The business's postal address, its employer (deductions) file number and an optional business
licence with its expiry date. None of them is required to use the product: the readiness card
shows what each one unlocks (a tax invoice needs the address, payroll needs the employer file)
and the dashboard reminds the owner 60 days before the licence expires. Nothing here blocks.

Revision ID: 0103
Revises: 0101
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0103"
down_revision: str | None = "0101"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = (
    "address_line",
    "address_city",
    "employer_file_number",
    "business_license_number",
    "business_license_expires_on",
)


def upgrade() -> None:
    op.execute("""
        ALTER TABLE app.tenants
            ADD COLUMN address_line text CHECK (length(address_line) <= 200),
            ADD COLUMN address_city text CHECK (length(address_city) <= 100),
            ADD COLUMN employer_file_number text
                CHECK (employer_file_number ~ '^[0-9A-Za-z/-]{2,20}$'),
            ADD COLUMN business_license_number text
                CHECK (length(business_license_number) <= 40),
            ADD COLUMN business_license_expires_on date
    """)
    op.execute(f"GRANT UPDATE ({', '.join(COLUMNS)}) ON app.tenants TO app_api")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ({', '.join(COLUMNS)}) ON app.tenants FROM app_api")
    op.execute("""
        ALTER TABLE app.tenants
            DROP COLUMN address_line, DROP COLUMN address_city,
            DROP COLUMN employer_file_number, DROP COLUMN business_license_number,
            DROP COLUMN business_license_expires_on
    """)
