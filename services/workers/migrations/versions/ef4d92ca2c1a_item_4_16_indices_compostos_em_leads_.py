"""item 4.16 - indices compostos em leads (org, status, score)

Revision ID: ef4d92ca2c1a
Revises: 6204e37105bf
Create Date: 2026-08-11 15:26:24.234325

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ef4d92ca2c1a'
down_revision: Union[str, Sequence[str], None] = '6204e37105bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Índices compostos que cobrem os filtros mais usados na listagem/paginação
    # server-side (item 4.16): org + status + score e org + status + data.
    op.create_index('ix_leads_org_status_created', 'leads', ['organization_id', 'status', 'created_at'], unique=False)
    op.create_index('ix_leads_org_status_score', 'leads', ['organization_id', 'status', 'qualification_score'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_leads_org_status_score', table_name='leads')
    op.drop_index('ix_leads_org_status_created', table_name='leads')
