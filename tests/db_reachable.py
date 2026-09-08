"""Auxiliar de sondagem de Postgres para testes de persistência.

O conftest injeta uma `DATABASE_URL` dummy para os Settings não quebrarem no
import, mas isso faz os testes de banco acreditarem que há Postgres disponível.
Aqui verificamos se a URL é de fato alcançável; se não for, o teste deve ser
pulado (mesmo comportamento do e2e_outreach_cycle.py sem E2E_DATABASE_URL).
"""

from __future__ import annotations

import os


def database_url() -> str | None:
    """URL do banco para testes: prioriza E2E_DATABASE_URL e cai para DATABASE_URL."""
    return os.environ.get("E2E_DATABASE_URL") or os.environ.get("DATABASE_URL")


def is_database_reachable(url: str | None) -> bool:
    """True se a URL responde a uma conexão simples (timeout curto)."""
    if not url:
        return False
    try:
        from sqlalchemy import create_engine

        engine = create_engine(url, connect_args={"connect_timeout": 2})
        try:
            with engine.connect():
                pass
        finally:
            engine.dispose()
        return True
    except Exception:
        return False