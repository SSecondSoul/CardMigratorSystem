"""Accounts and separate ownership; never rewrite historical request/binding JSON."""
from alembic import op
from card_migration_system.persistence.accounts import metadata
revision = '0008_multi_user'
down_revision = '0007_modular_migration'
branch_labels = None
depends_on = None
def upgrade():
    metadata.create_all(op.get_bind())
def downgrade():
    raise RuntimeError('Restore an explicit verified backup; do not delete accounts or evidence')
