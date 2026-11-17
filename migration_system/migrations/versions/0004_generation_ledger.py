"""Isolated generation request/attempt/receipt/candidate ledger; no paid calls."""
from alembic import op
from card_migration_system.persistence.generations import metadata

revision = '0004_generation_ledger'
down_revision = '0003_ssm_extractions'
branch_labels = None
depends_on = None


def upgrade():
    metadata.create_all(op.get_bind())


def downgrade():
    raise RuntimeError('Destructive downgrade is not exposed; restore an explicit verified backup')
