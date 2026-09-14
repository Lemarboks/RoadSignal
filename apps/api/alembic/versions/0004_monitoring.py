"""Persist the isolated monitoring workspace and its operator review history."""
from alembic import op
from sqlalchemy import select

from app.database.models import MonitoringState

revision = "0004"
down_revision = "0003"


def upgrade():
    connection = op.get_bind()
    table = MonitoringState.__table__
    # 0001 creates current metadata on fresh installations.
    table.create(connection, checkfirst=True)
    if connection.execute(select(table.c.id).where(table.c.id == "demo")).first() is None:
        connection.execute(table.insert().values(id="demo", payload={}))


def downgrade():
    MonitoringState.__table__.drop(op.get_bind(), checkfirst=True)
