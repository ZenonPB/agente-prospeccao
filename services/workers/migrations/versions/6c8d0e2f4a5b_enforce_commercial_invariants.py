"""enforce commercial invariants

Revision ID: 6c8d0e2f4a5b
Revises: 5b7c9d1e3f4a
"""
from typing import Sequence, Union

from alembic import op

revision: str = "6c8d0e2f4a5b"
down_revision: Union[str, Sequence[str], None] = "5b7c9d1e3f4a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOT VALID preserva dados legados, mas passa a impedir novas linhas/updates
    # inconsistentes. A validação integral fica condicionada ao preflight do UAT.
    op.execute(
        """
        ALTER TABLE leads
        ADD CONSTRAINT ck_leads_lost_reason_required
        CHECK (status <> 'PERDIDO' OR lost_reason IS NOT NULL)
        NOT VALID
        """
    )

    # Job sem tenant não é mais aceito pelo WebSocket. A mesma regra passa a ser
    # protegida para novas gravações sem derrubar deploy por legado já existente.
    op.execute(
        """
        ALTER TABLE jobs
        ADD CONSTRAINT ck_jobs_organization_required
        CHECK (organization_id IS NOT NULL)
        NOT VALID
        """
    )

    # Unicidade de conversão precisa ser garantia do banco. Se já houver dado
    # duplicado, abortamos a migration de forma explícita em vez de apagar ou
    # escolher um registro automaticamente.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM conversions
                GROUP BY lead_id, COALESCE(offer_key, 'unknown')
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'conversions contém duplicatas por lead/oferta; deduplicação exige decisão humana';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_conversions_lead_offer
        ON conversions (lead_id, COALESCE(offer_key, 'unknown'))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_conversions_lead_offer")
    op.execute(
        "ALTER TABLE jobs DROP CONSTRAINT IF EXISTS ck_jobs_organization_required"
    )
    op.execute(
        "ALTER TABLE leads DROP CONSTRAINT IF EXISTS ck_leads_lost_reason_required"
    )
