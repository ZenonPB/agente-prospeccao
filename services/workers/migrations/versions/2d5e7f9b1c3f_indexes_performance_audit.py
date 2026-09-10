"""Revision ID: 2d5e7f9b1c3f
Revises: 2c4e6f8a0d3e

Índices de performance identificados na auditoria do banco (onda 3):
- FKs usadas em leituras quentes (org-scoped, por lead/campanha) sem índice
  → seq scan em produção (enrichments.lead_id é o caso mais claro: é usado
  em cada detalhe de lead; jobs tinha apenas a chave primária).
- Índice parcial para o claim da fila (`_CLAIM_SQL` executa
  `WHERE status = 'PENDING' ORDER BY created_at LIMIT 1 FOR UPDATE SKIP
  LOCKED`) — sem índice, a fila varre e ordena toda a tabela.

Idempotente: cada índice é criado somente se ainda não existir.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2d5e7f9b1c3f"
down_revision: Union[str, Sequence[str], None] = "2c4e6f8a0d3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_INDEXES = (
    ("ix_enrichments_lead_id", "enrichments", ["lead_id"]),
    ("ix_jobs_campaign_id", "jobs", ["campaign_id"]),
    ("ix_jobs_organization_id", "jobs", ["organization_id"]),
    ("ix_leads_company_id", "leads", ["company_id"]),
    ("ix_persons_organization_id", "persons", ["organization_id"]),
    ("ix_persons_company_id", "persons", ["company_id"]),
    ("ix_event_opportunities_lead_id", "event_opportunities", ["lead_id"]),
    ("ix_commercial_outcomes_lead_id", "commercial_outcomes", ["lead_id"]),
    ("ix_notifications_lead_id", "notifications", ["lead_id"]),
)


def _index_exists(bind, table: str, name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(item["name"] == name for item in inspector.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    for name, table, columns in _INDEXES:
        if not _index_exists(bind, table, name):
            op.create_index(name, table, columns)
    if not _index_exists(bind, "jobs", "ix_jobs_pending_claim"):
        # A fila reclama apenas jobs PENDING por antiguidade (FOR UPDATE SKIP
        # LOCKED) — o índice parcial faz o claim em O(1) sem tocar o restante.
        op.create_index(
            "ix_jobs_pending_claim",
            "jobs",
            ["created_at"],
            postgresql_where=sa.text("status = 'PENDING'"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _index_exists(bind, "jobs", "ix_jobs_pending_claim"):
        op.drop_index("ix_jobs_pending_claim", table_name="jobs")
    for name, table, _columns in reversed(_INDEXES):
        if _index_exists(bind, table, name):
            op.drop_index(name, table_name=table)