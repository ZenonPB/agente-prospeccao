#!/usr/bin/env bash
# Ambiente de desenvolvimento local SEM root (Postgres embarcado + API + Web).
#
# Uso:
#   scripts/dev.sh start      # sobe Postgres, API (8000) e Web (3001)
#   scripts/dev.sh stop       # para tudo
#   scripts/dev.sh status     # mostra o que está rodando
#
# Pré-requisitos (configurados nesta máquina):
#   - Postgres 16 embarcado em ~/.local/agente-prospeccao (binários zonky)
#   - venvs em services/api/venv e services/workers/venv
#   - .env na raiz do repo (credenciais de banco e chaves de API)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PG_ROOT="${PG_ROOT:-$HOME/.local/agente-prospeccao}"
PG_BIN="$PG_ROOT/bin"
PGDATA="$PG_ROOT/pgdata"
PG_LOG="$PG_ROOT/pg.log"
API_LOG="$REPO_ROOT/services/api/uvicorn.log"
WEB_LOG="$REPO_ROOT/apps/web/next-dev.log"

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3001}"

pg_is_up() {
  "$PG_BIN/pg_ctl" -D "$PGDATA" status >/dev/null 2>&1
}

api_is_up() {
  [ -n "$(pgrep -f "uvicorn main:app.*$API_PORT" 2>/dev/null || true)" ]
}

web_is_up() {
  [ -n "$(pgrep -f "next.*dev" 2>/dev/null || true)" ]
}

pg_start() {
  if pg_is_up; then
    echo "PostgreSQL já está rodando."
  else
    "$PG_BIN/pg_ctl" -D "$PGDATA" -l "$PG_LOG" -o "-p 5432 -k /tmp -c listen_addresses=127.0.0.1" start
    echo "PostgreSQL iniciado (127.0.0.1:5432)."
  fi
}

api_start() {
  if api_is_up; then
    echo "API já está rodando."
    return
  fi
  cd "$REPO_ROOT/services/api"
  nohup ./venv/bin/uvicorn main:app --host 127.0.0.1 --port "$API_PORT" > "$API_LOG" 2>&1 &
  echo "API iniciando em http://127.0.0.1:$API_PORT/docs (log: $API_LOG)"
}

web_start() {
  if web_is_up; then
    echo "Web já está rodando."
    return
  fi
  cd "$REPO_ROOT/apps/web"
  nohup npm run dev > "$WEB_LOG" 2>&1 &
  echo "Web iniciando em http://localhost:$WEB_PORT (log: $WEB_LOG)"
}

pg_stop() {
  if pg_is_up; then
    "$PG_BIN/pg_ctl" -D "$PGDATA" stop
    echo "PostgreSQL parado."
  else
    echo "PostgreSQL não está rodando."
  fi
}

api_stop() {
  pkill -f "uvicorn main:app" 2>/dev/null && echo "API parada." || echo "API não está rodando."
}

web_stop() {
  pkill -f "next.*dev" 2>/dev/null && echo "Web parada." || echo "Web não está rodando."
}

status() {
  pg_is_up && echo "PostgreSQL:  rodando (127.0.0.1:5432)" || echo "PostgreSQL:  PARADO"
  api_is_up && echo "API:         rodando (http://127.0.0.1:$API_PORT)" || echo "API:         PARADA"
  web_is_up && echo "Web:         rodando (http://localhost:$WEB_PORT)" || echo "Web:         PARADA"
}

case "${1:-start}" in
  start)
    pg_start
    api_start
    web_start
    echo
    status
    ;;
  stop)
    web_stop
    api_stop
    pg_stop
    ;;
  status)
    status
    ;;
  *)
    echo "Uso: $0 {start|stop|status}" >&2
    exit 1
    ;;
esac
