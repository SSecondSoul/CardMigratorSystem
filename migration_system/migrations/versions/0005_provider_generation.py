"""Recorded provider-transport protocol; live dispatch remains disabled."""
from alembic import op
from card_migration_system.persistence.provider_generations import metadata

revision = '0005_provider_generation'
down_revision = '0004_generation_ledger'
branch_labels = None
depends_on = None


def upgrade():
    metadata.create_all(op.get_bind())


def downgrade():
    raise RuntimeError('Destructive downgrade is not exposed; restore an explicit verified backup')
