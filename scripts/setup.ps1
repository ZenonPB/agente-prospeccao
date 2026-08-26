# ============================================================================
# setup.ps1 — Setup completo do ambiente de desenvolvimento para Windows
# (SEM Docker). Equivalente ao scripts/setup.sh.
#
# Faz tudo de uma vez e é IDEMPOTENTE (pode rodar quantas vezes quiser):
#   1. Detecta um PostgreSQL já rodando na porta 5432; se não houver, baixa e
#      extrai o PostgreSQL EMBARCADO (binários zonky, sem instalar nada).
#   2. initdb + inicia o Postgres embarcado em 127.0.0.1:<porta>.
#   3. Cria/atualiza os venvs (services/api + services/workers) e instala deps.
#   4. Cria o .env na raiz (se não existir) com JWT_SECRET gerado.
#   5. Cria o banco <DBName> (se DATABASE_URL for local).
#   6. Roda alembic upgrade head + seed dos templates de scoring.
#   7. Cria o apps/web/.env.local com NEXTAUTH_SECRET.
#   8. npm ci se node_modules estiver ausente.
#
# Depois de rodar, suba tudo com:  .\scripts\dev.ps1 start
# Acesse http://localhost:3001 e crie sua conta em /register.
#
# Como rodar (PowerShell):
#   powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
#   (ou, se a policy já permitir scripts:  .\scripts\setup.ps1)
#
# Parâmetros opcionais:
#   -PGRoot     diretório do Postgres embarcado (padrão $HOME\.local\agente-prospeccao)
#   -DBName     nome do banco (padrão agente_prospeccao)
#   -DBUser     usuário do banco (padrão postgres)
#   -DBPort     porta do Postgres embarcado (padrão 5432; só usada se não houver PG)
#   -StartDev   após concluir, já sobe tudo (equivalente a dev.ps1 start)
#   -SkipDeps   não instala/atualiza venvs nem npm ci (para re-execuções rápidas)
# ============================================================================

param(
    [string]$PGRoot   = (Join-Path $HOME ".local\agente-prospeccao"),
    [string]$DBName   = "agente_prospeccao",
    [string]$DBUser   = "postgres",
    [int]   $DBPort   = 5432,
    [string]$PGVersion = "16.14.0",
    [switch]$StartDev,
    [switch]$SkipDeps
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot

# Console em UTF-8 (acentos do PT-BR corretos em qualquer janela) + acelera
# downloads do PowerShell (sem renderização de progresso).
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$ProgressPreference = 'SilentlyContinue'

# ---------------------------------------------------------------------------
# Helpers de saída
# ---------------------------------------------------------------------------
function Write-Step { param([string]$Msg) Write-Host "`n=== $Msg ===" -ForegroundColor Cyan }
function Write-OK   { param([string]$Msg) Write-Host "[OK] $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg) Write-Host "[AVISO] $Msg" -ForegroundColor Yellow }
function Write-Err  { param([string]$Msg) Write-Host "[ERRO] $Msg" -ForegroundColor Red }

# ---------------------------------------------------------------------------
# Validações básicas
# ---------------------------------------------------------------------------
if ($RepoRoot -match '[ ]' -or $RepoRoot -match '[^\x20-\x7E]') {
    Write-Err "O caminho do repositório contém espaços ou caracteres especiais/acentos:"
    Write-Err "  $RepoRoot"
    Write-Err "O Next.js falha (Internal Server Error) com esses caminhos no Windows."
    Write-Err "SOLUÇÃO: mova/clone o repositório para um caminho sem espaços e sem acentos"
    Write-Err "  (ex.: C:\code\agente-prospeccao) e rode o setup novamente."
    exit 1
}

# Resolve o Python (python ou py -3)
$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
$PYPrefix = @()
if (-not $PythonExe) {
    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) { $PythonExe = $pyCmd.Source; $PYPrefix = @("-3") }
}
if (-not $PythonExe) {
    Write-Err "Python não encontrado. Instale o Python 3.12+ (python.org) e marque 'Add to PATH'."
    exit 1
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Err "Node.js não encontrado. Instale o Node 20+ (nodejs.org) e marque 'Add to PATH'."
    exit 1
}

# Confere a versão do Python
try {
    $pyVer = (& $PythonExe @PYPrefix -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')" | Select-Object -Last 1)
    Write-Host "Python: $pyVer | Node: $((node --version))" -ForegroundColor Gray
} catch { }

# ---------------------------------------------------------------------------
# Helpers utilitários
# ---------------------------------------------------------------------------
function Test-TcpPort {
    param([int]$Port, [int]$TimeoutMs = 800)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        $ok = $async.AsyncWaitHandle.WaitOne($TimeoutMs)
        if ($ok) { $client.EndConnect($async) }
        $client.Close()
        return $ok
    } catch { return $false }
}

function Get-FileSha1 {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return "" }
    return (Get-FileHash -Path $Path -Algorithm SHA1).Hash
}

# ---------------------------------------------------------------------------
# 1) PostgreSQL — usa o que já estiver rodando ou baixa o embarcado (zonky)
# ---------------------------------------------------------------------------
$PG_EXTERNAL = Test-TcpPort $DBPort
$PG_BIN = $null
$PG_DATA = $null
$PG_LOG = $null
$PG_USED_PORT = $DBPort
$EMBEDDED = $false

function Setup-Postgres {
    if ($PG_EXTERNAL) {
        Write-OK "PostgreSQL detectado em 127.0.0.1:$DBPort (usando o existente — nada a instalar)"
        return
    }

    # ----- embarcado (zonky) -----
    $EMBEDDED = $true
    $PG_ROOT = $PGRoot
    $PG_LOG = Join-Path $PG_ROOT "pg.log"

    if (-not (Test-Path "$PG_ROOT\pgsql\bin\initdb.exe")) {
        Write-Step "Baixando PostgreSQL $PGVersion embarcado (zonky, sem Docker)"
        New-Item -ItemType Directory -Force -Path $PG_ROOT | Out-Null
        $jar = Join-Path $PG_ROOT "pg-$PGVersion.jar"
        $url = "https://repo1.maven.org/maven2/io/zonky/test/postgres/embedded-postgres-binaries-windows-amd64/$PGVersion/embedded-postgres-binaries-windows-amd64-$PGVersion.jar"
        Write-Host "  Baixando $url" -ForegroundColor Gray
        if (-not (Test-Path $jar)) {
            # curl.exe (nativo do Windows 10+) é muito mais rápido que
            # Invoke-WebRequest; usa-o quando disponível.
            $curl = (Get-Command curl.exe -ErrorAction SilentlyContinue).Source
            if ($curl) {
                & $curl -fSL --retry 3 -o $jar $url 2>$null
                if ($LASTEXITCODE -ne 0) { Write-Err "Falha ao baixar $url"; exit 1 }
            } else {
                Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $jar
            }
        }

        Write-Step "Extraindo binários"
        $extract = Join-Path $PG_ROOT "extract"
        if (Test-Path $extract) { Remove-Item -Recurse -Force $extract }
        # Jar é um zip: o ZipFile do .NET lê independente da extensão (o
        # Expand-Archive exigiria .zip).
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [System.IO.Compression.ZipFile]::ExtractToDirectory($jar, $extract)
        $txz = Get-ChildItem -Path $extract -Filter "*.txz" | Select-Object -First 1
        if (-not $txz) { Write-Err "Arquivo .txz não encontrado no jar zonky."; exit 1 }
        # Extrai o .tar.xz — tar.exe (nativo do Windows 10+) é bem mais rápido;
        # cai para o lzma do próprio Python quando o tar não existir.
        $tarx = (Get-Command tar.exe -ErrorAction SilentlyContinue).Source
        if ($tarx) {
            & $tarx -xf $txz.FullName -C $extract 2>$null
            if ($LASTEXITCODE -ne 0) {
                & $PythonExe @PYPrefix -c "import tarfile; tarfile.open(r'$($txz.FullName)','r:xz').extractall(r'$extract')"
            }
        } else {
            & $PythonExe @PYPrefix -c "import tarfile; tarfile.open(r'$($txz.FullName)','r:xz').extractall(r'$extract')"
        }
        $initdb = Get-ChildItem -Path $extract -Filter "initdb.exe" -Recurse | Select-Object -First 1
        if (-not $initdb) { Write-Err "initdb.exe não encontrado após extração."; exit 1 }
        $binDir = $initdb.DirectoryName
        $srcRoot = Split-Path $binDir -Parent

        # Normaliza para um caminho estável (PG_ROOT\pgsql\bin), qualquer que
        # seja o aninhamento do .txz, e remove o diretório temporário.
        $stable = Join-Path $PG_ROOT "pgsql"
        if (Test-Path (Join-Path $stable "bin\initdb.exe")) {
            $PG_BIN = Join-Path $stable "bin"
        } else {
            if (Test-Path $stable) { Remove-Item -Recurse -Force $stable }
            New-Item -ItemType Directory -Force -Path $stable | Out-Null
            Copy-Item -Recurse -Force (Join-Path $srcRoot "bin") (Join-Path $stable "bin")
            foreach ($d in @("share", "lib")) {
                if (Test-Path (Join-Path $srcRoot $d)) {
                    Copy-Item -Recurse -Force (Join-Path $srcRoot $d) (Join-Path $stable $d)
                }
            }
            $PG_BIN = Join-Path $stable "bin"
        }
        Remove-Item -Recurse -Force $extract
        Remove-Item -Force $jar
        Write-OK "Binários extraídos em $PG_BIN"
    } else {
        $PG_BIN = Join-Path $PG_ROOT "pgsql\bin"
        Write-OK "PostgreSQL embarcado já está baixado ($PG_BIN)"
    }

    $PG_DATA = Join-Path $PG_ROOT "pgdata"
    # Backends do postgres resolvem DLLs a partir do PATH — expor o bin embarcado
    # evita falha de inicialização (0xC0000142) em outras máquinas.
    $env:Path = "$PG_BIN;$env:Path"
    if (-not (Test-Path (Join-Path $PG_DATA "PG_VERSION"))) {
        Write-Step "initdb (auth trust, porta $PG_USED_PORT)"
        $pg_ctl = Join-Path $PG_BIN "pg_ctl.exe"
        # Se a porta escolhida estiver ocupada, avança para uma livre.
        while (Test-TcpPort $PG_USED_PORT) { $PG_USED_PORT++ }
        & (Join-Path $PG_BIN "initdb.exe") -D $PG_DATA -U $DBUser --auth=trust --encoding=UTF8 --locale=C | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Err "initdb falhou."; exit 1 }
        Write-OK "Data dir criado: $PG_DATA"
    }

    # Sobe se ainda não estiver no ar (o initdb acima pode ter mudado a porta)
    & (Join-Path $PG_BIN "pg_ctl.exe") -D $PG_DATA status *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Step "Iniciando PostgreSQL embarcado (127.0.0.1:$PG_USED_PORT)"
        & (Join-Path $PG_BIN "pg_ctl.exe") -D $PG_DATA -l $PG_LOG -o "-p $PG_USED_PORT -c listen_addresses=127.0.0.1" start
        if ($LASTEXITCODE -ne 0) { Write-Err "pg_ctl start falhou. Veja $PG_LOG"; exit 1 }
    }
    # Idempotência: usa a porta que o data dir realmente configurou
    $conf = Join-Path $PG_DATA "postgresql.conf"
    if (Test-Path $conf) {
        $m = Select-String -Path $conf -Pattern '^port\s*=\s*(\d+)' | Select-Object -First 1
        if ($m) { $PG_USED_PORT = [int]$m.Matches[0].Groups[1].Value }
    }
    Write-OK "PostgreSQL embarcado rodando em 127.0.0.1:$PG_USED_PORT"
}

# ---------------------------------------------------------------------------
# 2) venvs + dependências (idempotente via sha1 do requirements)
# ---------------------------------------------------------------------------
function Install-Venv {
    param([string]$Service)
    $dir = Join-Path $RepoRoot "services\$Service"
    $req = Join-Path $dir "requirements.txt"
    $venv = Join-Path $dir "venv"
    $marker = Join-Path $venv ".requirements.sha1"
    $pyExe = Join-Path $venv "Scripts\python.exe"

    $needsInstall = $true
    if (Test-Path $pyExe) {
        # Reinstala se o requirements mudou desde a última vez
        $old = if (Test-Path $marker) { (Get-Content $marker -Raw).Trim() } else { "" }
        $new = Get-FileSha1 $req
        if ($old -eq $new) { $needsInstall = $false }
    }

    if (-not $needsInstall) {
        Write-OK "venv de $Service já instalado"
        return
    }

    if ($SkipDeps) {
        Write-Warn "SkipDeps ativo — pulando dependências de $Service"
        return
    }

    if (-not (Test-Path $pyExe)) {
        Write-Step "Criando venv de $Service"
        & $Python -m venv $venv
    } else {
        Write-Step "Atualizando dependências de $Service"
    }
    & $pyExe -m pip install --upgrade pip -q
    & $pyExe -m pip install -r $req -q
    if ($LASTEXITCODE -ne 0) { Write-Err "pip install falhou em $Service"; exit 1 }
    (Get-FileSha1 $req) | Set-Content -Path $marker
    Write-OK "Dependências de $Service instaladas"
}

# ---------------------------------------------------------------------------
# 3) .env na raiz (só cria se não existir)
# ---------------------------------------------------------------------------
function Setup-Env {
    $envPath = Join-Path $RepoRoot ".env"
    if (Test-Path $envPath) {
        Write-OK ".env já existe (não sobrescrito)"
        return
    }

    Write-Step "Criando .env na raiz"
    # Gera 3 segredos de uma vez (JWT, NEXTAUTH, FERNET) com o próprio Python
    $secrets = & $PythonExe @PYPrefix -c "import secrets,base64,os;print(secrets.token_hex(32));print(secrets.token_hex(32));print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
    $jwt = $secrets[0].Trim()
    $webSecret = $secrets[1].Trim()
    $fernet = $secrets[2].Trim()

    $content = @"
# ===== PostgreSQL (embarcado em 127.0.0.1:$PG_USED_PORT ou existente) =====
POSTGRES_USER=$DBUser
POSTGRES_PASSWORD=
POSTGRES_DB=$DBName
DATABASE_URL=postgresql://${DBUser}:@127.0.0.1:$PG_USED_PORT/$DBName

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
"@
    Set-Content -Path $envPath -Value $content -Encoding UTF8
    Write-OK ".env criado — preencha GROQ_API_KEY e GOOGLE_API_KEY nele"
}

# ---------------------------------------------------------------------------
# 4) banco (cria se DATABASE_URL apontar para o Postgres local)
# ---------------------------------------------------------------------------
function Ensure-Database {
    Write-Step "Garantindo banco '$DBName'"
    $workersPy = Join-Path $RepoRoot "services\workers\venv\Scripts\python.exe"
    if (-not (Test-Path $workersPy)) { Write-Err "venv dos workers não existe — rode sem -SkipDeps."; exit 1 }
    $script = @"
import os, sys, urllib.parse, psycopg2
url = ""
envpath = r"$RepoRoot\.env"
if os.path.exists(envpath):
    for line in open(envpath, encoding="utf-8"):
        if line.startswith("DATABASE_URL="):
            url = line.split("=", 1)[1].strip(); break
if not url:
    url = "postgresql://postgres:@127.0.0.1:5432/$DBName"
p = urllib.parse.urlparse(url)
host = p.hostname or "127.0.0.1"
if host not in ("127.0.0.1", "localhost"):
    print("  DATABASE_URL aponta para host remoto (%s) - pulando criacao local" % host); sys.exit(0)
target = (p.path or "/$DBName").lstrip("/") or "$DBName"
maint = (url.rsplit('?', 1)[0]).rsplit('/', 1)[0] + "/postgres"
conn = psycopg2.connect(maint)
conn.autocommit = True
cur = conn.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target,))
if cur.fetchone():
    print("  banco '%s' ja existe" % target)
else:
    cur.execute('CREATE DATABASE "%s"' % target)
    print("  banco '%s' criado" % target)
cur.close(); conn.close()
"@
    $tmp = Join-Path $env:TEMP "agente_create_db_$PID.py"
    Set-Content -Path $tmp -Value $script -Encoding UTF8
    try {
        & $workersPy $tmp
        if ($LASTEXITCODE -ne 0) { Write-Err "Falha ao garantir o banco."; exit 1 }
    } finally {
        Remove-Item -Force $tmp -ErrorAction SilentlyContinue
    }
}

# ---------------------------------------------------------------------------
# 5) migrations + seed
# ---------------------------------------------------------------------------
function Run-Migrations {
    $workersPy = Join-Path $RepoRoot "services\workers\venv\Scripts\python.exe"
    Write-Step "Aplicando migrations (alembic upgrade head)"
    Push-Location (Join-Path $RepoRoot "services\workers")
    try {
        & $workersPy -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { Write-Err "alembic upgrade head falhou."; exit 1 }
        Write-Step "Seed de templates de scoring"
        & $workersPy -m src.seeds.scoring_templates
        if ($LASTEXITCODE -ne 0) { Write-Err "Seed falhou."; exit 1 }
    } finally {
        Pop-Location
    }
    Write-OK "Migrations e seed aplicados"
}

# ---------------------------------------------------------------------------
# 6) apps/web/.env.local (NEXTAUTH_SECRET)
# ---------------------------------------------------------------------------
function Setup-WebEnv {
    $envPath = Join-Path $RepoRoot "apps\web\.env.local"
    if (Test-Path $envPath) {
        Write-OK "apps/web/.env.local já existe"
        return
    }
    $secret = (& $PythonExe @PYPrefix -c "import secrets;print(secrets.token_hex(32))")[0].Trim()
    Set-Content -Path $envPath -Value "NEXTAUTH_SECRET=$secret`nNEXT_PUBLIC_API_URL=http://localhost:8000`n" -Encoding UTF8
    Write-OK "apps/web/.env.local criado (NEXTAUTH_SECRET)"
}

# ---------------------------------------------------------------------------
# 7) node_modules
# ---------------------------------------------------------------------------
function Setup-WebDeps {
    if (Test-Path (Join-Path $RepoRoot "apps\web\node_modules")) {
        Write-OK "node_modules já presente"
        return
    }
    if ($SkipDeps) { Write-Warn "SkipDeps ativo — pulando npm ci"; return }
    Write-Step "npm ci em apps/web"
    Push-Location (Join-Path $RepoRoot "apps\web")
    try {
        & npm ci
        if ($LASTEXITCODE -ne 0) { Write-Err "npm ci falhou."; exit 1 }
    } finally {
        Pop-Location
    }
}

# ===========================================================================
Write-Host "=== Setup do Prospect.ai (Windows, sem Docker) ===" -ForegroundColor Cyan
Write-Host "Repositório: $RepoRoot"
Write-Host "Postgres:    $PGRoot (porta $DBPort, banco $DBName)" -ForegroundColor Gray

Setup-Postgres
Install-Venv "workers"
Install-Venv "api"
Setup-Env
Ensure-Database
Run-Migrations
Setup-WebEnv
Setup-WebDeps

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host " Setup concluído!" -ForegroundColor Green
Write-Host "----------------------------------------------------------------------" -ForegroundColor Gray
Write-Host " Subir tudo:      .\scripts\dev.ps1 start"
Write-Host " Status:          .\scripts\dev.ps1 status"
Write-Host " Parar tudo:      .\scripts\dev.ps1 stop"
Write-Host ""
Write-Host " Web:             http://localhost:3001   (crie sua conta em /register)"
Write-Host " API (docs):      http://localhost:8000/docs"
Write-Host ""
Write-Host " Próximos passos:"
Write-Host "  1. Edite o .env da raiz e preencha GROQ_API_KEY e GOOGLE_API_KEY"
Write-Host "     (HUNTER_API_KEY opcional para e-mail de decisor)."
Write-Host "  2. Reinicie a API após preencher as chaves: dev.ps1 stop && start."
Write-Host "======================================================================" -ForegroundColor Green
Write-Host ""

if ($StartDev) {
    Write-Step "Iniciando tudo (-StartDev)"
    & (Join-Path $PSScriptRoot "dev.ps1") start
}
