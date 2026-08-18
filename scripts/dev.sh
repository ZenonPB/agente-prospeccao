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

# Evita o "Internal Server Error" no dev do Next.js causado por caminhos com espaços ou acentos
if ! LC_ALL=C expr "$REPO_ROOT" : '^[ -~]*$' >/dev/null || [[ "$REPO_ROOT" =~ " " ]]; then
  echo "=======================================================================" >&2
  echo "ERRO CRÍTICO: Caminho do repositório inválido para execução!" >&2
  echo "-----------------------------------------------------------------------" >&2
  echo "O caminho atual contém espaços ou caracteres especiais/acentos:" >&2
  echo "  $REPO_ROOT" >&2
  echo "" >&2
  echo "O Next.js (tanto Webpack quanto Turbopack) falha internamente com" >&2
  echo "'Internal Server Error' (Cannot find module) quando executado em caminhos" >&2
  echo "com espaços ou caracteres especiais (como 'Área de trabalho')." >&2
  echo "" >&2
  echo "SOLUÇÃO:" >&2
  echo "1. Mova ou clone o repositório para um diretório sem espaços e sem acentos." >&2
  echo "   Exemplo: /home/aluno/code/agente-prospeccao" >&2
  echo "2. Rode o ./scripts/setup.sh novamente a partir do novo local e depois o dev.sh." >&2
  echo "=======================================================================" >&2
  exit 1
fi

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

port_pids() {
  ss -ltnp 2>/dev/null | grep ":${1} " | grep -oP 'pid=\K[0-9]+' | sort -u || true
}

web_is_up() {
  [ -n "$(port_pids "$WEB_PORT")" ]
}

pg_start() {
  if pg_is_up; then
    echo "PostgreSQL já está rodando."
  else
    "$PG_BIN/pg_ctl" -D "$PGDATA" -l "$PG_LOG" -o "-p 5432 -k /tmp -c listen_addresses=127.0.0.1" start
    echo "PostgreSQL iniciado (127.0.0.1:5432)."
  fi
}

# Espera uma porta TCP estar escutando (timeout em segundos, default 30).
wait_for_up() {
  local port="$1" label="$2" seconds="${WAIT_TIMEOUT:-30}" i
  for i in $(seq 1 "$seconds"); do
    if [ -n "$(port_pids "$port")" ]; then
      return 0
    fi
    sleep 1
  done
  echo "AVISO: $label não abriu a porta $port em ${seconds}s — verifique $3" >&2
  return 1
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

# Seed idempotente dos templates de scoring: garante que mudanças nos
# templates default cheguem ao banco em cada start (mesmo comportamento do
# setup.sh). Seguro rodar sempre — usa service_label como chave e só atualiza.
seed_templates() {
  echo "Seed de templates de scoring"
  ( cd "$REPO_ROOT/services/workers" && ./venv/bin/python -m src.seeds.scoring_templates )
}

web_start() {
  if web_is_up; then
    echo "Web já está rodando."
    return
  fi
  cd "$REPO_ROOT/apps/web"
  # Cache persistente do Turbopack já serviu chunks corrompidos (500
  # MODULE_NOT_FOUND em internals de next/*). Sempre subir com compilação limpa.
  rm -rf .next
  setsid nohup npm run dev > "$WEB_LOG" 2>&1 < /dev/null &
  disown 2>/dev/null || true
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
  local pids
  pids="$(port_pids "$WEB_PORT")"
  if [ -n "$pids" ]; then
    kill $pids 2>/dev/null || true
    echo "Web parada."
  else
    echo "Web não está rodando."
  fi
}

status() {
  pg_is_up && echo "PostgreSQL:  rodando (127.0.0.1:5432)" || echo "PostgreSQL:  PARADO"
  api_is_up && echo "API:         rodando (http://127.0.0.1:$API_PORT)" || echo "API:         PARADA"
  web_is_up && echo "Web:         rodando (http://localhost:$WEB_PORT)" || echo "Web:         PARADA"
}

case "${1:-start}" in
  start)
    pg_start
    seed_templates
    api_start
    wait_for_up "$API_PORT" "API" "$API_LOG"
    web_start
    wait_for_up "$WEB_PORT" "Web" "$WEB_LOG" || true
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
