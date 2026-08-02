"""add lead assignment, activity trail and conversion attribution

Revision ID: 6b3c2a1d9e8f4
Revises: 9a7b6c5d4e3f2
Create Date: 2026-08-01

Fase X1 (atribuição + trilha):
- `leads.assigned_to_id` (FK users, nullable) + `leads.assigned_at` — dono do
  lead (consultor responsável), atribuído manualmente no kanban.
- Tabela `lead_activities` — trilha de quem fez o quê (atribuição, mudança de
  status, mensagem, contato, reunião, conversão). Base do BI por consultor e
  da auditoria.
- Enum `lead_activity_action` (CREATED, ASSIGNED, UNASSIGNED, STATUS_CHANGED,
  MESSAGE_GENERATED, CONTACTED, RESPONDED, MEETING_SCHEDULED, CONVERTED).
- `conversions.user_id` (quem fechou) e `conversions.assigned_to_id` (quem
  trabalhava o lead no momento da conversão).

Não altera dados existentes (colunas novas são nullable).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ENUM


revision: str = '6b3c2a1d9e8f4'
down_revision: Union[str, Sequence[str], None] = '9a7b6c5d4e3f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- Enum de ações da trilha ---
    action_enum = ENUM(
        'CREATED', 'ASSIGNED', 'UNASSIGNED', 'STATUS_CHANGED',
        'MESSAGE_GENERATED', 'CONTACTED', 'RESPONDED',
        'MEETING_SCHEDULED', 'CONVERTED',
        name='lead_activity_action',
    )
    action_enum.create(conn, checkfirst=True)
    action_col = ENUM(
        'CREATED', 'ASSIGNED', 'UNASSIGNED', 'STATUS_CHANGED',
        'MESSAGE_GENERATED', 'CONTACTED', 'RESPONDED',
        'MEETING_SCHEDULED', 'CONVERTED',
        name='lead_activity_action', create_type=False,
    )

    # --- Atribuição no lead ---
    op.add_column('leads', sa.Column('assigned_to_id', UUID(as_uuid=True),
                                     sa.ForeignKey('users.id'), nullable=True))
    op.add_column('leads', sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_leads_assigned_to_id', 'leads', ['assigned_to_id'])

    # --- Trilha de atividades ---
    lead_status_col = ENUM(
        'NOVO', 'ANALISADO', 'QUALIFICADO', 'DESQUALIFICADO',
        'CONTATADO', 'RESPONDIDO', 'REUNIAO_MARCADA', 'REUNIAO_FEITA',
        'PROPOSTA_ENVIADA', 'PERDIDO',
        name='lead_status', create_type=False,
    )
    op.create_table(
        'lead_activities',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('lead_id', UUID(as_uuid=True),
                  sa.ForeignKey('leads.id'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id'), nullable=True),
        sa.Column('action', action_col, nullable=False),
        sa.Column('status_from', lead_status_col, nullable=True),
        sa.Column('status_to', lead_status_col, nullable=True),
        sa.Column('detail', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
    )
    op.create_index('ix_lead_activities_lead_id', 'lead_activities', ['lead_id'])
    op.create_index('ix_lead_activities_user_id', 'lead_activities', ['user_id'])
    op.create_index('ix_lead_activities_created_at', 'lead_activities', ['created_at'])

    # --- Atribuição de conversão ---
    op.add_column('conversions', sa.Column('user_id', UUID(as_uuid=True),
                                           sa.ForeignKey('users.id'), nullable=True))
    op.add_column('conversions', sa.Column('assigned_to_id', UUID(as_uuid=True),
                                           sa.ForeignKey('users.id'), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()

    op.drop_column('conversions', 'assigned_to_id')
    op.drop_column('conversions', 'user_id')

    op.drop_index('ix_lead_activities_created_at', table_name='lead_activities')
    op.drop_index('ix_lead_activities_user_id', table_name='lead_activities')
    op.drop_index('ix_lead_activities_lead_id', table_name='lead_activities')
    op.drop_table('lead_activities')
    ENUM(name='lead_activity_action').drop(conn, checkfirst=True)

    op.drop_index('ix_leads_assigned_to_id', table_name='leads')
    op.drop_column('leads', 'assigned_at')
    op.drop_column('leads', 'assigned_to_id')
