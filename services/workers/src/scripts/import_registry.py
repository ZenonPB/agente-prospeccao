"""Importa snapshot do universo empresarial (dados públicos CNPJ/Receita).

E2E operacional da Fase 1B: arquivos layout-Receita → registry_* (global),
com ledger, checkpoint e contadores. Idempotente e reiniciável.

Uso (CWD services/workers, por causa do env_file relativo):
    python -m src.scripts.import_registry --snapshot-month 2026-08 \\
        --estabelecimentos /dados/2026-08/ESTABELE0 \\
        --empresas /dados/2026-08/EMPRESA0 \\
        --cnaes /dados/2026-08/CNAE
"""
import argparse
import logging
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from config.settings import settings  # noqa: E402
from database.session import SessionLocal  # noqa: E402
from services.registry.importer import RegistryFileSpec, RegistryImporter  # noqa: E402

logger = logging.getLogger(__name__)


def _specs(args: argparse.Namespace) -> list[RegistryFileSpec]:
    specs: list[RegistryFileSpec] = []
    for kind, paths in (
        ("estabelecimentos", args.estabelecimentos or []),
        ("empresas", args.empresas or []),
        ("cnaes", args.cnaes or []),
    ):
        for path in paths:
            specs.append(RegistryFileSpec(
                table_kind=kind, path=path, file_name=os.path.basename(path)))
    return specs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-month", required=True, help="AAAAMM do snapshot (ex. 2026-08)")
    parser.add_argument("--source", default="receita_cnpj")
    parser.add_argument("--estabelecimentos", action="append", default=[])
    parser.add_argument("--empresas", action="append", default=[])
    parser.add_argument("--cnaes", action="append", default=[])
    parser.add_argument("--batch-size", type=int, default=settings.REGISTRY_BATCH_SIZE)
    parser.add_argument("--encoding", default=settings.REGISTRY_ENCODING)
    args = parser.parse_args()
    specs = _specs(args)
    if not specs:
        parser.error("informe ao menos um arquivo (--estabelecimentos/--empresas/--cnaes)")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    db = SessionLocal()
    try:
        snapshot = RegistryImporter(db, batch_size=args.batch_size, encoding=args.encoding).import_snapshot(
            source=args.source, snapshot_month=args.snapshot_month, files=specs)
    finally:
        db.close()
    logger.info(
        "snapshot %s/%s: %s (processed=%d inserted=%d updated=%d unchanged=%d rejected=%d failed=%d)",
        snapshot.source, snapshot.snapshot_month, snapshot.status, snapshot.processed,
        snapshot.inserted, snapshot.updated, snapshot.unchanged, snapshot.rejected, snapshot.failed,
    )
    return 0 if snapshot.status == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
