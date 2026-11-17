"""Real migration job, call, evidence and manual feedback ledgers."""
from alembic import op
from card_migration_system.persistence.migrations import jobs, files, calls, feedback
revision = '0007_modular_migration'
down_revision = '0006_generation_approvals'
branch_labels = None
depends_on = None

def upgrade():
    for table in (jobs, files, calls, feedback): table.create(op.get_bind())

def downgrade():
    raise RuntimeError('Restore a verified backup instead of destructive downgrade')
