"""Register real SSM extraction evidence without rewriting fixture runs."""
from alembic import op
from card_migration_system.persistence.ssm_extractions import metadata

revision = '0003_ssm_extractions'
down_revision = '0002_worker_health'
branch_labels = None
depends_on = None


def upgrade():
    metadata.create_all(op.get_bind())


def downgrade():
    raise RuntimeError('Destructive downgrade is not exposed; restore an explicit verified backup')
