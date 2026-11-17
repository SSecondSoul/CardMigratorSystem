"""Initial bounded development schema; schema_v1 is immutable migration input."""
from alembic import op
from card_migration_system.persistence.schema_v1 import metadata

revision = "0001_development_slice"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    metadata.create_all(op.get_bind())


def downgrade():
    raise RuntimeError("Destructive downgrade is not exposed; restore an explicit verified backup")
