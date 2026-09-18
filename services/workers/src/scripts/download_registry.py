"""Baixa os arquivos de um snapshot oficial para o disco local.

Etapa de infraestrutura (opt-in): manifesto → disco. A importação para o
PostgreSQL continua separada (`import_registry --manifest`).

Uso (CWD services/workers):
    python -m src.scripts.download_registry \\
        --manifest /dados/2026-08/manifest.json \\
        --dest /dados/2026-08 \\
        --write-manifest /dados/2026-08/manifest.local.json
"""
import argparse
import asyncio
import logging
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from services.registry.downloader import (  # noqa: E402
    DownloadError,
    SnapshotDownloader,
    manifest_download_specs,
    manifest_with_observed,
)
from services.registry.manifest import ManifestError, dump_manifest, load_manifest  # noqa: E402

logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="manifesto JSON do snapshot")
    parser.add_argument("--dest", required=True, help="diretório de destino dos arquivos")
    parser.add_argument("--write-manifest", default=None,
                        help="grava manifesto com bytes/sha256 observados")
    parser.add_argument("--max-attempts", type=int, default=4)
    parser.add_argument("--timeout-total", type=float, default=1800.0)
    args = parser.parse_args()

    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as exc:
        parser.error(f"manifesto inválido: {exc}")
    try:
        specs = manifest_download_specs(manifest, args.dest)
    except DownloadError as exc:
        parser.error(f"specs inválidas: {exc}")
    os.makedirs(args.dest, exist_ok=True)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if manifest.origin_kind != "receita_oficial":
        logger.warning("origem declarada: %s (%s) — não é a fonte oficial",
                       manifest.origin_kind, manifest.origin_url)
    downloader = SnapshotDownloader(
        max_attempts=args.max_attempts, timeout_total=args.timeout_total)
    try:
        results = asyncio.run(downloader.download_all(specs))
    except DownloadError as exc:
        logger.error("download falhou: %s", exc)
        return 1
    total = sum(result.bytes for result in results)
    logger.info("snapshot %s: %d arquivos, %d bytes em %s",
                manifest.snapshot_month, len(results), total, args.dest)
    if args.write_manifest:
        observed = {result.file_name: (result.bytes, result.sha256) for result in results}
        with open(args.write_manifest, "w", encoding="utf-8") as handle:
            handle.write(dump_manifest(manifest_with_observed(manifest, observed)))
        logger.info("manifesto observado gravado em %s", args.write_manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
