"""Content studio (module `social_studio`): connected social accounts and their numbers.

A business connects its social networks (Facebook, Instagram, TikTok, YouTube, Google Business
and more) and sees one analytics dashboard. We keep only summarized, public numbers of the
business itself (followers, reach, views, engagement, its own posts, audience shares), never
private messages and never personal data of followers. Provider tokens are encrypted in
`secrets` (app/providers/secrets.py) and never leave the API.

Our own daily history is kept because some networks only give 90 days back.

Revision ID: 0093
Revises: 0082
Create Date: 2026-10-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0093"
down_revision: str | None = "0082"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "social_accounts",
    "social_metrics_daily",
    "social_posts",
    "social_post_metrics",
    "social_audience",
)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE app.social_accounts (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id      uuid NOT NULL REFERENCES app.tenants (id) ON DELETE CASCADE,
            location_id    uuid,
            provider       text NOT NULL CHECK (length(provider) BETWEEN 1 AND 40),
            network        text NOT NULL CHECK (length(network) BETWEEN 1 AND 40),
            external_id    text NOT NULL CHECK (length(external_id) BETWEEN 1 AND 200),
            name           text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
            avatar_url     text,
            status         text NOT NULL DEFAULT 'connected'
                           CHECK (status IN ('connected', 'needs_reauth')),
            is_demo        boolean NOT NULL DEFAULT false,
            scopes         text[] NOT NULL DEFAULT '{}',
            secrets        bytea,
            connected_by   uuid,
            last_synced_at timestamptz,
            created_at     timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, network, external_id),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, location_id) REFERENCES app.locations (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("""
        CREATE TABLE app.social_metrics_daily (
            tenant_id     uuid NOT NULL,
            account_id    uuid NOT NULL,
            day           date NOT NULL,
            followers     integer NOT NULL DEFAULT 0 CHECK (followers >= 0),
            reach         integer NOT NULL DEFAULT 0 CHECK (reach >= 0),
            impressions   integer NOT NULL DEFAULT 0 CHECK (impressions >= 0),
            video_views   integer NOT NULL DEFAULT 0 CHECK (video_views >= 0),
            engagements   integer NOT NULL DEFAULT 0 CHECK (engagements >= 0),
            profile_views integer NOT NULL DEFAULT 0 CHECK (profile_views >= 0),
            link_clicks   integer NOT NULL DEFAULT 0 CHECK (link_clicks >= 0),
            calls         integer NOT NULL DEFAULT 0 CHECK (calls >= 0),
            directions    integer NOT NULL DEFAULT 0 CHECK (directions >= 0),
            searches      integer NOT NULL DEFAULT 0 CHECK (searches >= 0),
            reviews_new   integer NOT NULL DEFAULT 0 CHECK (reviews_new >= 0),
            rating        numeric(3, 2) CHECK (rating BETWEEN 1 AND 5),
            PRIMARY KEY (account_id, day),
            FOREIGN KEY (tenant_id, account_id) REFERENCES app.social_accounts (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute("""
        CREATE TABLE app.social_posts (
            id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id     uuid NOT NULL,
            account_id    uuid NOT NULL,
            external_id   text NOT NULL CHECK (length(external_id) BETWEEN 1 AND 200),
            kind          text NOT NULL CHECK (kind IN ('post', 'reel', 'story', 'video')),
            published_at  timestamptz NOT NULL,
            thumbnail_url text,
            permalink     text,
            caption       text CHECK (length(caption) <= 300),
            UNIQUE (account_id, external_id),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, account_id) REFERENCES app.social_accounts (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX social_posts_recent ON app.social_posts (tenant_id, published_at DESC)"
    )
    # The latest cumulative numbers of a post (a snapshot, refreshed by the sync).
    op.execute("""
        CREATE TABLE app.social_post_metrics (
            post_id       uuid PRIMARY KEY,
            tenant_id     uuid NOT NULL,
            views         integer NOT NULL DEFAULT 0 CHECK (views >= 0),
            likes         integer NOT NULL DEFAULT 0 CHECK (likes >= 0),
            comments      integer NOT NULL DEFAULT 0 CHECK (comments >= 0),
            shares        integer NOT NULL DEFAULT 0 CHECK (shares >= 0),
            saves         integer NOT NULL DEFAULT 0 CHECK (saves >= 0),
            avg_watch_sec integer CHECK (avg_watch_sec >= 0),
            updated_at    timestamptz NOT NULL DEFAULT now(),
            FOREIGN KEY (tenant_id, post_id) REFERENCES app.social_posts (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    # Weekly snapshot of the audience: one row per slice (an age band, a gender, a city...).
    op.execute("""
        CREATE TABLE app.social_audience (
            tenant_id   uuid NOT NULL,
            account_id  uuid NOT NULL,
            captured_on date NOT NULL,
            dimension   text NOT NULL CHECK (dimension IN ('age', 'gender', 'city', 'country')),
            label       text NOT NULL CHECK (length(label) BETWEEN 1 AND 100),
            share_bp    integer NOT NULL CHECK (share_bp BETWEEN 0 AND 10000),
            PRIMARY KEY (account_id, captured_on, dimension, label),
            FOREIGN KEY (tenant_id, account_id) REFERENCES app.social_accounts (tenant_id, id)
                ON DELETE CASCADE
        )
    """)
    # Every foreign key and every tenant table is indexed (tests/test_database_security.py).
    op.execute(
        "CREATE INDEX social_accounts_branch ON app.social_accounts (tenant_id, location_id)"
    )
    op.execute(
        "CREATE INDEX social_metrics_account ON app.social_metrics_daily (tenant_id, account_id)"
    )
    op.execute("CREATE INDEX social_posts_account ON app.social_posts (tenant_id, account_id)")
    op.execute(
        "CREATE INDEX social_post_metrics_post ON app.social_post_metrics (tenant_id, post_id)"
    )
    op.execute(
        "CREATE INDEX social_audience_account ON app.social_audience (tenant_id, account_id)"
    )
    for table in TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON app.{table} TO app_api")
        op.execute(f"ALTER TABLE app.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant ON app.{table} TO app_api
            USING (tenant_id = app.current_tenant_id())
            WITH CHECK (tenant_id = app.current_tenant_id())
        """)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE app.{table}")
