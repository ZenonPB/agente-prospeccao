"""Registry file identity: hash SHA-256 por arquivo (tamanho não é identidade).

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
"""
from alembic import op
import sqlalchemy as sa

revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("registry_import_files", sa.Column("sha256", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("registry_import_files", "sha256")
