
#!/usr/bin/env bash
# Setup completo do ambiente de desenvolvimento SEM root.
#
# Faz tudo de uma vez e é IDEMPOTENTE (pode rodar quantas vezes quiser):
#   1. Baixa e extrai PostgreSQL embarcado (binários zonky, sem sudo)
#   2. initdb + inicia o Postgres em 127.0.0.1:5432
#   3. Cria venvs (workers + api) e instala as dependências
#   4. Cria o .env na raiz (se não existir) com JWT_SECRET gerado
#   5. Cria o banco `agente_prospeccao` (se DATABASE_URL for local)
#   6. Roda alembic upgrade head + seed dos templates de scoring
#   7. Cria o apps/web/.env.local com NEXTAUTH_SECRET
#   8. npm ci se node_modules estiver ausente
#
# Depois de rodar, suba tudo com:  scripts/dev.sh start
# Em seguida acesse http://localhost:3001 e crie sua conta em /register.
#
# Variáveis opcionais:
#   PG_ROOT       diretório do Postgres embarcado (padrão ~/.local/agente-prospeccao)
#   DB_NAME       nome do banco (padrão agente_prospeccao)
#   PG_VERSION    versão dos binários zonky (padrão 16.14.0)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Evita o "Internal Server Error" no dev do Next.js causado por caminhos com espaços ou acentos
if ! LC_ALL=C expr "$REPO_ROOT" : '^[ -~]*$' >/dev/null || [[ "$REPO_ROOT" =~ " " ]]; then
  echo "=======================================================================" >&2
  echo "ERRO CRÍTICO DE SETUP: Caminho do repositório inválido!" >&2
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
  echo "2. Rode o ./scripts/setup.sh novamente a partir do novo local." >&2
  echo "=======================================================================" >&2
  exit 1
fi

PG_ROOT="${PG_ROOT:-$HOME/.local/agente-prospeccao}"
PG_BIN="$PG_ROOT/bin"
PGDATA="$PG_ROOT/pgdata"
PG_VERSION="${PG_VERSION:-16.14.0}"
PG_JAR_URL="https://repo1.maven.org/maven2/io/zonky/test/postgres/embedded-postgres-binaries-linux-amd64/${PG_VERSION}/embedded-postgres-binaries-linux-amd64-${PG_VERSION}.jar"

DB_USER="${DB_USER:-postgres}"
DB_NAME="${DB_NAME:-agente_prospeccao}"
DB_PORT="${DB_PORT:-5432}"

step() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m%s\033[0m\n' "$*"; }

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "ERRO: '$1' não encontrado. Instale '$2' antes." >&2; exit 1; }
}

# ---------------------------------------------------------------------------
# 1) PostgreSQL embarcado
# ---------------------------------------------------------------------------
setup_postgres() {
  require curl curl
  require tar tar
  require unzip unzip

  if [ ! -x "$PG_BIN/initdb" ]; then
    step "Baixando PostgreSQL ${PG_VERSION} (embarcado, sem root)"
    mkdir -p "$PG_ROOT"
    curl -fsSL -o "$PG_ROOT/pg16.jar" "$PG_JAR_URL"
    ( cd "$PG_ROOT" && unzip -oq pg16.jar && tar -xJf postgres-linux-x86_64.txz )
    ok "Binários extraídos em $PG_ROOT"
  else
    ok "PostgreSQL já está baixado em $PG_ROOT"
  fi

  if [ ! -d "$PGDATA" ]; then
    step "initdb (auth trust, porta $DB_PORT)"
    "$PG_BIN/initdb" -D "$PGDATA" -U "$DB_USER" --auth=trust --encoding=UTF8 --no-locale >/dev/null
    ok "Data dir criado: $PGDATA"
  fi

  if ! "$PG_BIN/pg_ctl" -D "$PGDATA" status >/dev/null 2>&1; then
    step "Iniciando PostgreSQL"
    "$PG_BIN/pg_ctl" -D "$PGDATA" -l "$PG_ROOT/pg.log" \
      -o "-p $DB_PORT -k /tmp -c listen_addresses=127.0.0.1" start
  fi
  ok "PostgreSQL rodando em 127.0.0.1:$DB_PORT"
}

# ---------------------------------------------------------------------------
# 2) venvs + dependências (idempotente via sha1 do requirements)
# ---------------------------------------------------------------------------
install_venv() {
  local service="$1"
  local dir="$REPO_ROOT/services/$service"
  local req="$dir/requirements.txt"
  local marker="$dir/venv/.requirements.sha1"

  local python_ok=0
  if [ -x "$dir/venv/bin/python" ] && [ -f "$dir/venv/bin/pip" ]; then
    # Verifica se os scripts do venv (como o pip) apontam para a pasta atual (evita caminhos antigos)
    if grep -q "$dir/venv/bin/python" "$dir/venv/bin/pip"; then
      python_ok=1
    fi
  fi

  if [ "$python_ok" -eq 0 ]; then
    step "Criando venv do serviço $service"
    rm -rf "$dir/venv"
    python3 -m venv "$dir/venv"
    "$dir/venv/bin/pip" install --upgrade pip -q
    "$dir/venv/bin/pip" install -r "$req" -q
    sha1sum "$req" | cut -d' ' -f1 > "$marker"
    ok "Dependências de $service instaladas"
  else
    local old new
    old=$(cat "$marker" 2>/dev/null || true)
    new=$(sha1sum "$req" | cut -d' ' -f1)
    if [ "$old" != "$new" ]; then
      step "Atualizando dependências de $service"
      "$dir/venv/bin/pip" install -r "$req" -q
      sha1sum "$req" | cut -d' ' -f1 > "$marker"
      ok "Dependências de $service atualizadas"
    else
      ok "venv de $service já instalado"
    fi
  fi
}

# ---------------------------------------------------------------------------
# 3) .env na raiz (cria só se não existir)
# ---------------------------------------------------------------------------
setup_env() {
  if [ -f "$REPO_ROOT/.env" ]; then
    ok ".env já existe (não sobrescrito)"
    return
  fi
  step "Criando .env na raiz"
  local jwt secret fernet
  jwt=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  secret=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  fernet=$(python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
  cat > "$REPO_ROOT/.env" <<EOF
# ===== PostgreSQL local (sem root, binários zonky em $PG_ROOT) =====
POSTGRES_USER=$DB_USER
POSTGRES_PASSWORD=
POSTGRES_DB=$DB_NAME
DATABASE_URL=postgresql://$DB_USER:@127.0.0.1:$DB_PORT/$DB_NAME

PGADMIN_EMAIL=admin@local.dev
PGADMIN_PASSWORD=admin

# ===== Chaves de API (preencha para coletar e qualificar) =====
GROQ_API_KEY=
GOOGLE_API_KEY=
HUNTER_API_KEY=

# ===== API =====
JWT_SECRET=$jwt
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
CADENCE_POLL_SECONDS=60
EMAIL_WEBHOOK_SECRET=
SECRETS_ENCRYPTION_KEY=$fernet
RESET_TOKEN_EXPIRY_HOURS=2
APP_BASE_URL=http://localhost:3001

# ===== SMTP (opcional — só para envio real de e-mail) =====
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@prospect.ai
SMTP_FROM_NAME=Prospect.ai
EOF
  ok ".env criado — preencha GROQ_API_KEY e GOOGLE_API_KEY nele"
}

# ---------------------------------------------------------------------------
# 4) banco (cria se DATABASE_URL apontar para o Postgres local)
# ---------------------------------------------------------------------------
create_database() {
  step "Garantindo banco '$DB_NAME'"
  "$REPO_ROOT/services/workers/venv/bin/python" - "$DB_NAME" "$REPO_ROOT" <<'PY'
import os, sys, urllib.parse

db_name, repo_root = sys.argv[1], sys.argv[2]
url = os.environ.get("DATABASE_URL") or ""
if not url:
    dotenv = os.path.join(repo_root, ".env")
    if os.path.exists(dotenv):
        for line in open(dotenv):
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1]
                break
if not url:
    url = "postgresql://postgres:@127.0.0.1:5432/agente_prospeccao"

parsed = urllib.parse.urlparse(url)
host = parsed.hostname or "127.0.0.1"
if host not in ("127.0.0.1", "localhost"):
    print(f"  DATABASE_URL aponta para host remoto ({host}) — pulando criação local")
    sys.exit(0)

port = parsed.port or 5432
user = parsed.username or "postgres"
target = (parsed.path or "/agente_prospeccao").lstrip("/") or "agente_prospeccao"

import psycopg2
conn = psycopg2.connect(host=host, port=port, user=user, dbname="postgres")
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target,))
if cur.fetchone():
    print(f"  banco '{target}' já existe")
else:
    cur.execute(f'CREATE DATABASE "{target}"')
    print(f"  banco '{target}' criado")
cur.close(); conn.close()
PY
}

# ---------------------------------------------------------------------------
# 5) migrations + seed
# ---------------------------------------------------------------------------
run_migrations() {
  step "Aplicando migrations (alembic upgrade head)"
  ( cd "$REPO_ROOT/services/workers" && ./venv/bin/alembic upgrade head )
  step "Seed de templates de scoring"
  ( cd "$REPO_ROOT/services/workers" && ./venv/bin/python -m src.seeds.scoring_templates )
}

# ---------------------------------------------------------------------------
# 6) .env.local do web (NEXTAUTH_SECRET)
# ---------------------------------------------------------------------------
setup_web_env() {
  if [ -f "$REPO_ROOT/apps/web/.env.local" ]; then
    ok "apps/web/.env.local já existe"
    return
  fi
  local secret
  secret=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  printf 'NEXTAUTH_SECRET=%s\nNEXT_PUBLIC_API_URL=http://localhost:8000\n' "$secret" \
    > "$REPO_ROOT/apps/web/.env.local"
  ok "apps/web/.env.local criado (NEXTAUTH_SECRET)"
}

# ---------------------------------------------------------------------------
# 7) node_modules
# ---------------------------------------------------------------------------
setup_web_deps() {
  if [ -d "$REPO_ROOT/apps/web/node_modules" ]; then
    ok "node_modules já presente"
    return
  fi
  step "npm ci em apps/web"
  ( cd "$REPO_ROOT/apps/web" && npm ci )
}

# ===========================================================================
main() {
  require python3 "Python 3.10+"
  require sha1sum coreutils

  echo "Repositório: $REPO_ROOT"
  echo "Postgres:    $PG_ROOT (porta $DB_PORT, banco $DB_NAME)"

  setup_postgres
  install_venv workers
  install_venv api
  setup_env
  create_database
  run_migrations
  setup_web_env
  setup_web_deps

  cat <<'EOF'

======================================================================
 Setup concluído!
----------------------------------------------------------------------
 Subir tudo:      scripts/dev.sh start
 Status:          scripts/dev.sh status
 Parar tudo:      scripts/dev.sh stop

 Web:             http://localhost:3001   (crie sua conta em /register)
 API (docs):      http://localhost:8000/docs

 Próximos passos:
 1. Edite o .env da raiz e preencha GROQ_API_KEY e GOOGLE_API_KEY
    (HUNTER_API_KEY opcional para e-mail de decisor).
 2. Reinicie a API após preencher as chaves: scripts/dev.sh stop && scripts/dev.sh start
======================================================================
EOF
}

main
