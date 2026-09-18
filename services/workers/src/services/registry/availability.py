"""AVAILABLE COMPANY: regra única de universo consultável do Registry.

Uma empresa está disponível quando pertence ao membership do snapshot
resolvido para a consulta (default: ACTIVE). Search, health, admin e
métricas devem usar este contrato em vez de reimplementar a regra.
"""
from __future__ import annotations

from typing import Any

import sqlalchemy as sa


def membership_cnpj_select(snapshot_id: Any) -> Any:
    """SELECT de CNPJs membros do snapshot (para IN/membership join)."""
    from database.models import RegistrySnapshotMember

    return sa.select(RegistrySnapshotMember.cnpj).where(
        RegistrySnapshotMember.snapshot_id == snapshot_id)


def available_company_count(db: Any, snapshot_id: Any) -> int:
    """Conta empresas disponíveis no membership do snapshot."""
    subquery = membership_cnpj_select(snapshot_id).subquery()
    return int(db.execute(
        sa.select(sa.func.count()).select_from(subquery)
    ).scalar() or 0)
