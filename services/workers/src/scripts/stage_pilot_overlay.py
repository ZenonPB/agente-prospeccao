"""Prepara o overlay do piloto Araraquara (Landing Pages → psicologia).

Grava a versão do piloto como INATIVA e idempotente para a organização.
A ativação é humana e explícita, pelo fluxo existente de versões de oferta
(publicação/rollback) — este script nunca ativa sozinho.

Uso (CWD services/workers):
    python -m src.scripts.stage_pilot_overlay --org-id <uuid-da-organizacao>
"""
import argparse
import logging
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from database.models import Organization  # noqa: E402
from database.session import SessionLocal  # noqa: E402
from services.pilot.araraquara import (  # noqa: E402
    PILOT_OFFER_KEY,
    PILOT_VERSION,
    stage_pilot_overlay,
)

logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org-id", required=True, help="UUID da organização piloto")
    parser.add_argument("--version", default=PILOT_VERSION,
                        help="versão do overlay (padrão do piloto)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    db = SessionLocal()
    try:
        org = db.query(Organization).filter_by(id=args.org_id).first()
        if org is None:
            parser.error(f"organização não encontrada: {args.org_id}")
        row = stage_pilot_overlay(db, org.id, version=args.version)
    finally:
        db.close()
    logger.info("overlay %s/%s pronto (ativo=%s) para %s — ative pelo fluxo de versões",
                PILOT_OFFER_KEY, row.version, row.is_active, org.id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
