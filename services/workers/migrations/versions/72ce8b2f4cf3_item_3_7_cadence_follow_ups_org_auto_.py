"""cadence follow_ups + org auto_send + lead opt_out; playbook por vertical

Revision ID: 72ce8b2f4cf3
Revises: f3a4b5c6d7e8
Create Date: 2026-08-03 23:20:04.719491

Cadência de follow-up + envio:
- Tabela `follow_ups` — etapas da cadência dia 0/3/7/14 por lead
  (enums `follow_up_step` e `follow_up_status`; `channel` reusa `message_channel`).
- `organizations.auto_send_email` (default false) — opt-in de envio automático.
- `leads.opt_out` (default false) — LGPD opt-out.

Playbooks por vertical:
- `campaign_scoring_templates.playbook` (JSONB) — hooks/assuntos/objeções.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '72ce8b2f4cf3'
down_revision: Union[str, Sequence[str], None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE follow_up_step AS ENUM ('OPENING', 'FOLLOWUP_1', 'FOLLOWUP_2', 'CLOSING')")
    op.execute("CREATE TYPE follow_up_status AS ENUM ('PENDING', 'SENT', 'SKIPPED', 'CANCELLED')")

    op.create_table(
        'follow_ups',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('lead_id', sa.UUID(), nullable=False),
        sa.Column('step', postgresql.ENUM('OPENING', 'FOLLOWUP_1', 'FOLLOWUP_2', 'CLOSING', name='follow_up_step', create_type=False), nullable=False),
        sa.Column('channel', postgresql.ENUM('EMAIL', 'WHATSAPP', 'LINKEDIN', name='message_channel', create_type=False), nullable=True),
        sa.Column('subject', sa.String(length=255), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', postgresql.ENUM('PENDING', 'SENT', 'SKIPPED', 'CANCELLED', name='follow_up_status', create_type=False), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_follow_ups_lead_id', 'follow_ups', ['lead_id'], unique=False)
    op.create_index('ix_follow_ups_scheduled_at', 'follow_ups', ['scheduled_at'], unique=False)

    op.add_column(
        'campaign_scoring_templates',
        sa.Column('playbook', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'leads',
        sa.Column('opt_out', sa.Boolean(), server_default='false', nullable=False),
    )
    op.add_column(
        'organizations',
        sa.Column('auto_send_email', sa.Boolean(), server_default='false', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('organizations', 'auto_send_email')
    op.drop_column('leads', 'opt_out')
    op.drop_column('campaign_scoring_templates', 'playbook')
    op.drop_index('ix_follow_ups_scheduled_at', table_name='follow_ups')
    op.drop_index('ix_follow_ups_lead_id', table_name='follow_ups')
    op.drop_table('follow_ups')
    op.execute("DROP TYPE IF EXISTS follow_up_status")
    op.execute("DROP TYPE IF EXISTS follow_up_step")
