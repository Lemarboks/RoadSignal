"""Add production authentication and refresh-session fields safely."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "name" not in user_columns:
        op.add_column("users", sa.Column("name", sa.String(100), nullable=True))
        op.execute("UPDATE users SET name = split_part(email, '@', 1) WHERE name IS NULL")
        op.alter_column("users", "name", nullable=False)
    if "is_active" not in user_columns:
        op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))

    tables = [
        "users", "fleets", "fleet_members", "vehicles", "trips", "trip_locations",
        "routes", "route_segments", "incidents", "incident_confirmations",
        "incident_sources", "risk_scores", "alerts", "emergency_events", "audit_logs",
    ]
    for table in tables:
        columns = {column["name"] for column in sa.inspect(bind).get_columns(table)}
        if "updated_at" not in columns:
            op.add_column(table, sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

    user_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("users")}
    if "ix_users_email" not in user_indexes:
        op.create_index("ix_users_email", "users", ["email"])
    if "ix_users_role" not in user_indexes:
        op.create_index("ix_users_role", "users", ["role"])

    if "refresh_sessions" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "refresh_sessions",
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"])
        op.create_index("ix_refresh_sessions_token_hash", "refresh_sessions", ["token_hash"], unique=True)
        op.create_index("ix_refresh_sessions_expires_at", "refresh_sessions", ["expires_at"])


def downgrade():
    bind = op.get_bind()
    if "refresh_sessions" in sa.inspect(bind).get_table_names():
        op.drop_table("refresh_sessions")
    user_columns = {column["name"] for column in sa.inspect(bind).get_columns("users")}
    for column in ("is_active", "name"):
        if column in user_columns:
            op.drop_column("users", column)
