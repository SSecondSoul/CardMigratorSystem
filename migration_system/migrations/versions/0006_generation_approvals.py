"""Single-plan approval metadata and immutable action records; no dispatch."""
from alembic import op
from card_migration_system.persistence.generation_approvals import metadata

revision = '0006_generation_approvals'
down_revision = '0005_provider_generation'
branch_labels = None
depends_on = None


def upgrade():
    metadata.create_all(op.get_bind())


def downgrade():
    raise RuntimeError('Destructive downgrade is not exposed; restore an explicit verified backup')
