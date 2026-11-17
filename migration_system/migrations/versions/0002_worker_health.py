"""Add operational worker presence without changing the frozen initial schema."""
from alembic import op
from card_migration_system.persistence.worker_health import metadata

revision = "0002_worker_health"
down_revision = "0001_development_slice"
branch_labels = None
depends_on = None


def upgrade():
    metadata.create_all(op.get_bind())


def downgrade():
    raise RuntimeError("Destructive downgrade is not exposed; restore an explicit verified backup")
