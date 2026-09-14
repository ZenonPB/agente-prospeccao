#!/usr/bin/env bash
set -euo pipefail

: "${RESTORE_DATABASE_URL:?RESTORE_DATABASE_URL é obrigatório}"
BACKUP="${1:?informe o arquivo .backup}"

if [[ ! -s "$BACKUP" ]]; then
  echo "backup ausente ou vazio" >&2
  exit 2
fi
pg_restore --list "$BACKUP" >/dev/null
pg_restore --exit-on-error --no-owner --no-acl --clean --if-exists --dbname="$RESTORE_DATABASE_URL" "$BACKUP"
printf 'restore_ok=%s\n' "$RESTORE_DATABASE_URL"
