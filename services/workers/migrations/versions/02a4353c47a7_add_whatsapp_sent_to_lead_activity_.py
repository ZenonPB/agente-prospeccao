"""add_whatsapp_sent_to_lead_activity_action

Revision ID: 02a4353c47a7
Revises: f6b7c8d9e0f1
Create Date: 2026-08-10 20:59:39.904279

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '02a4353c47a7'
down_revision: Union[str, Sequence[str], None] = 'f6b7c8d9e0f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE lead_activity_action ADD VALUE IF NOT EXISTS 'WHATSAPP_SENT'")


def downgrade() -> None:
    pass
