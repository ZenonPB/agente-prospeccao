#!/usr/bin/env bash
# Backup do PostgreSQL (item 3.5 da auditoria).
#
# Uso (host com docker compose):
#   ./scripts/backup.sh            # backup local em ./backups
#   RETENTION_DAYS=7 ./scripts/backup.sh   # apaga dumps mais antigos que 7 dias
#   ./scripts/backup.sh --verify-restore  # restaura último dump em banco temporário e valida (item 4.15)
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

# ---------------------------------------------------------------------------
# Teste real de restore (item 4.15 da auditoria): restaura o dump mais recente
# em um banco TEMPORÁRIO e compara a contagem de linhas das tabelas principais
# com o banco de origem. Garante que o dump é íntegro e restaurável.
# ---------------------------------------------------------------------------
if [[ "${1:-}" == "--verify-restore" ]]; then
  LATEST="$(ls -t ${BACKUP_DIR}/prospeccao_*.dump 2>/dev/null | head -1)"
  if [[ -z "${LATEST}" ]]; then
    echo "ERRO: nenhum dump encontrado em ${BACKUP_DIR}. Rode ./scripts/backup.sh primeiro." >&2
    exit 1
  fi
  echo "Verificando restore do dump: ${LATEST}"

  if [[ -n "${DATABASE_URL:-}" ]]; then
    # Extrai host/porta/usuário/nome do banco a partir da URL.
    PGHOST="$(echo "${DATABASE_URL}" | sed -E 's#.*@([^:/]+).*#\1#')"
    PGPORT="$(echo "${DATABASE_URL}" | sed -E 's#.*:([0-9]+)/.*#\1#')"
    PGUSER="$(echo "${DATABASE_URL}" | sed -E 's#.*://([^:]+):.*#\1#')"
    SRC_DB="$(echo "${DATABASE_URL}" | sed -E 's#.*/([^/?]+).*#\1#')"
  else
    PGHOST="${PGHOST:-localhost}"
    PGPORT="${PGPORT:-5432}"
    PGUSER="${POSTGRES_USER:-postgres}"
    SRC_DB="${POSTGRES_DB:-prospeccao}"
  fi

  TEST_DB="prospeccao_restore_check"
  # Conecta via psql nativo quando há DATABASE_URL, senão via container `db`.
  _psql() {
    if [[ -n "${DATABASE_URL:-}" ]]; then
      psql "$@"
    else
      docker compose exec -T db psql -U "${PGUSER}" "$@"
    fi
  }

  echo "Criando banco temporário ${TEST_DB}..."
  _psql -d postgres -c "DROP DATABASE IF EXISTS ${TEST_DB};" >/dev/null
  _psql -d postgres -c "CREATE DATABASE ${TEST_DB};" >/dev/null

  echo "Restaurando dump em ${TEST_DB}..."
  if [[ -n "${DATABASE_URL:-}" ]]; then
    pg_restore --no-owner --exit-on-error -d "${DATABASE_URL%${SRC_DB}}${TEST_DB}" "${LATEST}"
  else
    docker compose exec -T db pg_restore -U "${PGUSER}" -d "${TEST_DB}" --no-owner --exit-on-error - < "${LATEST}"
  fi

  TABLES="organizations campaigns leads contacts enrichment messages follow_ups daily_sent_usage quota_usage"

  FAIL=0
  echo "Comparando contagens de linhas entre origem e restore..."
  for t in ${TABLES}; do
    SRC_COUNT="$(_psql -d "${SRC_DB}" -tAc "SELECT count(*) FROM ${t}")"
    DST_COUNT="$(_psql -d "${TEST_DB}" -tAc "SELECT count(*) FROM ${t}")"
    if [[ "${SRC_COUNT}" != "${DST_COUNT}" ]]; then
      echo "  [FALHA] ${t}: origem=${SRC_COUNT} restore=${DST_COUNT}"
      FAIL=1
    else
      echo "  [ok] ${t}: ${SRC_COUNT}"
    fi
  done

  echo "Removendo banco temporário..."
  _psql -d postgres -c "DROP DATABASE IF EXISTS ${TEST_DB};" >/dev/null

  if [[ "${FAIL}" == "1" ]]; then
    echo "ERRO: restore não confere com a origem." >&2
    exit 1
  fi
  echo "OK: restore validado (${LATEST})."
fi
