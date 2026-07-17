"""Initial SafeRoute schema (models are the source of column definitions)."""
from alembic import op
from app.database.models import Base
revision="0001"; down_revision=None
def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    bind=op.get_bind(); Base.metadata.create_all(bind)
    op.execute("CREATE INDEX IF NOT EXISTS ix_incidents_location ON incidents USING GIST (location)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_trip_locations_location ON trip_locations USING GIST (location)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_routes_geometry ON routes USING GIST (geometry)")
def downgrade(): Base.metadata.drop_all(op.get_bind())
