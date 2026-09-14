#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL é obrigatório}"
OUTPUT="${1:-/tmp/agente-prospeccao.backup}"

umask 077
pg_dump --format=custom --no-owner --no-acl --file="$OUTPUT" "$DATABASE_URL"
pg_restore --list "$OUTPUT" >/dev/null
printf 'backup_ok=%s\n' "$OUTPUT"
