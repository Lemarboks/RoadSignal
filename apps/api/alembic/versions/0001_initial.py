"""Create the MySQL 8 spatial schema from the current models."""
from alembic import op
from app.database.models import Base

revision = "0001"
down_revision = None

def upgrade():
    Base.metadata.create_all(op.get_bind())

def downgrade():
    Base.metadata.drop_all(op.get_bind())
