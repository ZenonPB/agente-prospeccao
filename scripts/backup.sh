#!/usr/bin/env bash
# Backup do PostgreSQL (item 3.5 da auditoria).
#
# Uso (host com docker compose):
#   ./scripts/backup.sh            # backup local em ./backups
#   RETENTION_DAYS=7 ./scripts/backup.sh   # apaga dumps mais antigos que 7 dias
#
# Com Postgres nativo (sem docker):
#   DATABASE_URL=postgresql://user:pass@host:5432/db ./scripts/backup.sh
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
STAMP="$(date +%F_%H%M%S)"

mkdir -p "${BACKUP_DIR}"

# Se DATABASE_URL estiver definida, usa psql direto; senão usa o container `db`.
if [[ -n "${DATABASE_URL:-}" ]]; then
  pg_dump --no-owner --format=custom "${DATABASE_URL}" -f "${BACKUP_DIR}/prospeccao_${STAMP}.dump"
else
  docker compose exec -T db pg_dump -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-prospeccao}" \
    --no-owner --format=custom -f "/backups/prospeccao_${STAMP}.dump"
  # o volume db_backups é montado em /backups no container do Postgres.
fi

echo "Backup criado: ${BACKUP_DIR}/prospeccao_${STAMP}.dump"

# Rotação
if command -v find >/dev/null 2>&1; then
  find "${BACKUP_DIR}" -name "prospeccao_*.dump" -mtime "+${RETENTION_DAYS}" -delete
  echo "Rotação: dumps com mais de ${RETENTION_DAYS} dias removidos."
fi

echo "Restauração (exemplo):"
echo "  pg_restore --clean --no-owner -d postgresql://user:pass@host:5432/db ${BACKUP_DIR}/prospeccao_${STAMP}.dump"
