"""Add fields used by persistent route, trip, and incident repositories."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"


def add_missing(table: str, name: str, column: sa.Column):
    existing = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}
    if name not in existing:
        op.add_column(table, column)


def upgrade():
    add_missing("routes", "external_id", sa.Column("external_id", sa.String(100)))
    add_missing("routes", "name", sa.Column("name", sa.String(160)))
    add_missing("routes", "duration_minutes", sa.Column("duration_minutes", sa.SmallInteger()))
    add_missing("routes", "distance_km", sa.Column("distance_km", sa.Numeric(8, 2)))
    add_missing("routes", "confidence", sa.Column("confidence", sa.Numeric(4, 3)))
    add_missing("routes", "risk_level", sa.Column("risk_level", sa.String(20)))
    add_missing("routes", "recommended", sa.Column("recommended", sa.Boolean(), server_default=sa.false()))
    add_missing("routes", "difference_from_fastest", sa.Column("difference_from_fastest", sa.SmallInteger(), server_default="0"))
    add_missing("routes", "breakdown", sa.Column("breakdown", postgresql.JSONB(), server_default="{}"))
    add_missing("routes", "factors", sa.Column("factors", postgresql.JSONB(), server_default="[]"))
    add_missing("routes", "explanation", sa.Column("explanation", sa.Text(), server_default=""))
    add_missing("routes", "segment_scores", sa.Column("segment_scores", postgresql.JSONB(), server_default="[]"))
    op.execute("UPDATE routes SET external_id=id::text, name='Stored route', duration_minutes=0, distance_km=0, confidence=0, risk_level='unknown' WHERE external_id IS NULL")
    for field in ("external_id", "name", "duration_minutes", "distance_km", "confidence", "risk_level", "recommended", "difference_from_fastest", "breakdown", "factors", "explanation", "segment_scores"):
        op.alter_column("routes", field, nullable=False)
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("routes")}
    if "ix_routes_external_id" not in indexes:
        op.create_index("ix_routes_external_id", "routes", ["external_id"], unique=True)

    add_missing("trips", "route_id", sa.Column("route_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("routes.id", ondelete="SET NULL")))
    add_missing("trips", "progress", sa.Column("progress", sa.SmallInteger(), nullable=False, server_default="0"))
    add_missing("trips", "safety_score", sa.Column("safety_score", sa.Numeric(5, 2), nullable=False, server_default="0"))
    add_missing("trips", "alerts", sa.Column("alerts", postgresql.JSONB(), nullable=False, server_default="[]"))
    add_missing("trips", "started_at", sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("trips")}
    if "ix_trips_route_id" not in indexes: op.create_index("ix_trips_route_id", "trips", ["route_id"])
    if "ix_trips_started_at" not in indexes: op.create_index("ix_trips_started_at", "trips", ["started_at"])

    add_missing("incidents", "confirmations", sa.Column("confirmations", sa.SmallInteger(), nullable=False, server_default="0"))
    add_missing("incidents", "disputes", sa.Column("disputes", sa.SmallInteger(), nullable=False, server_default="0"))
    add_missing("incidents", "status", sa.Column("status", sa.String(20), nullable=False, server_default="active"))
    add_missing("incidents", "abuse_flags", sa.Column("abuse_flags", postgresql.JSONB(), nullable=False, server_default="[]"))
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("incidents")}
    if "ix_incidents_status" not in indexes: op.create_index("ix_incidents_status", "incidents", ["status"])


def downgrade():
    pass
