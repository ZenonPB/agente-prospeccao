"""Fecha os gates de integridade comercial após o backfill verificável.

Revision ID: f8a9b0c1d2e3
Revises: f2b3c4d5e6f7
"""
from typing import Sequence, Union

from alembic import op


revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, Sequence[str], None] = "f2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Uma campanha só pode fornecer o workspace do job quando a relação é
    # determinística. Inconsistências existentes abortam a migration sem
    # escolher silenciosamente um tenant.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM jobs AS j
                JOIN campaigns AS c ON c.id = j.campaign_id
                WHERE j.organization_id IS NOT NULL
                  AND j.organization_id <> c.organization_id
            ) THEN
                RAISE EXCEPTION
                    'jobs possui campaign_id e organization_id de workspaces diferentes';
            END IF;
        END
        $$;
        """
    )

    # Backfill idempotente e observável: somente jobs sem workspace e com
    # campanha pertencente a exatamente um workspace são preenchidos.
    op.execute(
        """
        DO $$
        DECLARE
            backfilled_count bigint;
        BEGIN
            UPDATE jobs AS j
            SET organization_id = c.organization_id
            FROM campaigns AS c
            WHERE j.organization_id IS NULL
              AND j.campaign_id = c.id
              AND c.organization_id IS NOT NULL;
            GET DIAGNOSTICS backfilled_count = ROW_COUNT;
            RAISE NOTICE 'jobs.organization_id backfill: % registro(s)', backfilled_count;
        END
        $$;
        """
    )

    # Jobs sem campanha resolvível são órfãos e não podem ser atribuídos por
    # inferência. A exceção aborta a transação antes do SET NOT NULL.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM jobs
                WHERE organization_id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'jobs órfãos sem organization_id; backfill exige decisão explícita';
            END IF;
        END
        $$;
        """
    )

    # O SET NOT NULL só ocorre depois do backfill e da rejeição dos órfãos.
    op.execute(
        "ALTER TABLE jobs ALTER COLUMN organization_id SET NOT NULL"
    )
    op.execute(
        "ALTER TABLE jobs VALIDATE CONSTRAINT ck_jobs_organization_required"
    )
    op.execute(
        "ALTER TABLE leads VALIDATE CONSTRAINT ck_leads_lost_reason_required"
    )

    # As buscas canônicas de Person sempre começam pelo workspace e depois
    # avaliam CPF/e-mail exatos. Índices não únicos aceleram esse caminho sem
    # fabricar unicidade antes de uma análise de colisões no PostgreSQL.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_persons_org_document_cpf
        ON persons (organization_id, document_cpf)
        WHERE document_cpf IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_persons_org_email
        ON persons (organization_id, email)
        WHERE email IS NOT NULL
        """
    )


def downgrade() -> None:
    # Os checks pertencem à migration anterior e permanecem intactos. O
    # downgrade apenas reabre a coluna e remove os índices introduzidos aqui;
    # não desfaz o backfill nem apaga histórico.
    op.execute("DROP INDEX IF EXISTS ix_persons_org_email")
    op.execute("DROP INDEX IF EXISTS ix_persons_org_document_cpf")
    op.execute(
        "ALTER TABLE jobs ALTER COLUMN organization_id DROP NOT NULL"
    )
