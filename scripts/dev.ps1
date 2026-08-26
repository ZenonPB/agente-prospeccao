# ============================================================================
# dev.ps1 — Ambiente de desenvolvimento para Windows (SEM Docker).
#
# Uso:
#   .\scripts\dev.ps1 start      # sobe PostgreSQL, aplica migrations+seed,
#                                # API (8000) e Web (3001, mudável via WEB_PORT)
#   .\scripts\dev.ps1 stop       # para tudo (inclui o Postgres embarcado, se foi
#                                # ele quem subiu; um Postgres já existente fica)
#   .\scripts\dev.ps1 status     # mostra o que está rodando
#   .\scripts\dev.ps1 restart    # stop + start
#
# PostgreSQL:
#   - Se já houver um PostgreSQL respondendo na porta 5432, ele é usado como
#     está (nada é tocado).
#   - Senão, usa o PostgreSQL EMBARCADO criado pelo scripts\setup.ps1
#     (binários zonky em $HOME\.local\agente-prospeccao\pgsql).
#   - Se nem um nem outro existir, avisa para rodar o setup.ps1 primeiro.
# ============================================================================

param(
    [Parameter(Position = 0)]
    [string]$Action = 'start'
)

$ErrorActionPreference = 'Continue'
$RepoRoot = Split-Path -Parent $PSScriptRoot

# Console em UTF-8 (acentos do PT-BR corretos em qualquer janela).
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$API_PORT = if ($env:API_PORT) { $env:API_PORT } else { '8000' }
$WEB_PORT = if ($env:WEB_PORT) { $env:WEB_PORT } else { '3001' }

# Local do Postgres embarcado (mesmo padrão do setup.ps1)
$PGRoot  = Join-Path $HOME ".local\agente-prospeccao"
$PGData  = Join-Path $PGRoot "pgdata"
$PGBin   = Join-Path $PGRoot "pgsql\bin"
$PGLog   = Join-Path $PGRoot "pg.log"
# Marcador: diz que o Postgres embarcado foi iniciado POR ESTE script.
$PGMarker = Join-Path $env:TEMP "agente_dev_embedded_pg.txt"

$APILog  = Join-Path $RepoRoot "services\api\uvicorn.log"
$APILogErr = Join-Path $RepoRoot "services\api\uvicorn.err.log"
$WEBLog  = Join-Path $RepoRoot "apps\web\next-dev.log"
$WEBLogErr = Join-Path $RepoRoot "apps\web\next-dev.err.log"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Write-OK   { param([string]$M) Write-Host "[OK] $M" -ForegroundColor Green }
function Write-Warn { param([string]$M) Write-Host "[AVISO] $M" -ForegroundColor Yellow }
function Write-Info { param([string]$M) Write-Host "[..] $M" -ForegroundColor Cyan }

function Test-TcpPort {
    param([int]$Port, [int]$TimeoutMs = 1000)
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $a = $c.BeginConnect("127.0.0.1", $Port, $null, $null)
        $ok = $a.AsyncWaitHandle.WaitOne($TimeoutMs)
        if ($ok) { $c.EndConnect($a) }
        $c.Close()
        return $ok
    } catch { return $false }
}

function Wait-Port {
    param([int]$Port, [string]$Label, [int]$Seconds = 60)
    for ($i = 0; $i -lt $Seconds; $i++) {
        if (Test-TcpPort $Port) { return $true }
        Start-Sleep -Seconds 1
    }
    Write-Warn "$Label não abriu a porta $Port em ${Seconds}s."
    return $false
}

function Get-ListeningPids {
    param([int]$Port)
    try {
        return @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique)
    } catch { return @() }
}

function Test-ExternalPg     { Test-TcpPort 5432 }
function Test-EmbeddedPgUp   { (Test-Path "$PGBin\pg_ctl.exe") -and (Test-Path (Join-Path $PGData "PG_VERSION")) -and ((& "$PGBin\pg_ctl.exe" -D $PGData status 2>$null) -and $LASTEXITCODE -eq 0) }

# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------
function Start-Postgres {
    if (Test-ExternalPg) {
        Write-OK "PostgreSQL: usando o que já está rodando em 127.0.0.1:5432"
        return
    }
    if (Test-Path "$PGBin\pg_ctl.exe" -and (Test-Path (Join-Path $PGData "PG_VERSION"))) {
        if (-not (Test-EmbeddedPgUp)) {
            Write-Info "PostgreSQL embarcado iniciando (127.0.0.1:5432)"
            $env:Path = "$PGBin;$env:Path"
            & "$PGBin\pg_ctl.exe" -D $PGData -l $PGLog -o "-p 5432 -c listen_addresses=127.0.0.1" start 2>$null
            Start-Sleep -Seconds 2
        }
        if (Test-EmbeddedPgUp) {
            Write-OK "PostgreSQL embarcado rodando em 127.0.0.1:5432"
            Set-Content -Path $PGMarker -Value $PID
        } else {
            Write-Warn "Não consegui subir o Postgres embarcado. Veja $PGLog"
        }
        return
    }
    Write-Warn "PostgreSQL não encontrado (nem externo, nem embarcado). Rode .\scripts\setup.ps1 primeiro."
}

function Stop-Postgres {
    if ((Test-Path $PGMarker) -and (Test-EmbeddedPgUp)) {
        Write-Info "Parando PostgreSQL embarcado"
        & "$PGBin\pg_ctl.exe" -D $PGData stop 2>$null | Out-Null
        Remove-Item -Force $PGMarker -ErrorAction SilentlyContinue
        Write-OK "PostgreSQL embarcado parado."
    } else {
        Write-Info "PostgreSQL: mantendo o existente (não foi iniciado por este script)."
        Remove-Item -Force $PGMarker -ErrorAction SilentlyContinue
    }
}

# ---------------------------------------------------------------------------
# Banco — migrations + seed idempotentes (schema e templates sempre em dia)
# ---------------------------------------------------------------------------
function Invoke-DbMigrate {
    $workersPy = Join-Path $RepoRoot "services\workers\venv\Scripts\python.exe"
    if (-not (Test-Path $workersPy)) { Write-Warn "venv dos workers ausente — pulando migrations/seed. Rode .\scripts\setup.ps1."; return }
    Write-Info "Aplicando migrations (alembic upgrade head)"
    Push-Location (Join-Path $RepoRoot "services\workers")
    try {
        & $workersPy -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) { Write-Warn "alembic upgrade head falhou — veja mensagem acima."; return }
        & $workersPy -m src.seeds.scoring_templates
        if ($LASTEXITCODE -ne 0) { Write-Warn "seed de templates falhou — veja mensagem acima." }
    } finally {
        Pop-Location
    }
}

# ---------------------------------------------------------------------------
# API (uvicorn no venv)
# ---------------------------------------------------------------------------
function Test-ApiRunning { Test-TcpPort $API_PORT }

function Start-Api {
    if (Test-ApiRunning) { Write-OK "API já está rodando (http://localhost:$API_PORT)"; return }
    $venvPy = Join-Path $RepoRoot "services\api\venv\Scripts\python.exe"
    if (-not (Test-Path $venvPy)) { Write-Warn "venv da API não existe. Rode .\scripts\setup.ps1."; return }
    Write-Info "Iniciando API em http://localhost:$API_PORT/docs"
    $argsApi = @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", $API_PORT)
    Start-Process -FilePath $venvPy -ArgumentList $argsApi -WorkingDirectory (Join-Path $RepoRoot "services\api") `
        -RedirectStandardOutput $APILog -RedirectStandardError $APILogErr -WindowStyle Hidden | Out-Null
    if (-not (Wait-Port $API_PORT "API")) { Write-Warn "API não respondeu. Veja $APILog" }
    else { Write-OK "API no ar (http://localhost:$API_PORT/docs)" }
}

function Stop-Api {
    $pids = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match "uvicorn main:app" } |
        Select-Object -ExpandProperty ProcessId)
    foreach ($pid_ in $pids) { Stop-Process -Id $pid_ -Force -ErrorAction SilentlyContinue }
    if ($pids.Count -gt 0) { Write-OK "API parada." } else { Write-Info "API não estava rodando." }
}

# ---------------------------------------------------------------------------
# Web (Next.js dev)
# ---------------------------------------------------------------------------
function Test-WebRunning { Test-TcpPort $WEB_PORT }

function Start-Web {
    if (Test-WebRunning) { Write-OK "Web já está rodando (http://localhost:$WEB_PORT)"; return }
    $webDir = Join-Path $RepoRoot "apps\web"
    if (-not (Test-Path (Join-Path $webDir "node_modules"))) { Write-Warn "node_modules ausente. Rode .\scripts\setup.ps1."; return }
    Write-Info "Iniciando Web em http://localhost:$WEB_PORT"
    # Cache do Turbopack já serviu chunks corrompidos (500 MODULE_NOT_FOUND) —
    # sempre subir com compilação limpa.
    Remove-Item -Recurse -Force (Join-Path $webDir ".next") -ErrorAction SilentlyContinue
    Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "dev", "--", "-p", $WEB_PORT) -WorkingDirectory $webDir `
        -RedirectStandardOutput $WEBLog -RedirectStandardError $WEBLogErr -WindowStyle Hidden | Out-Null
    if (-not (Wait-Port $WEB_PORT "Web")) { Write-Warn "Web não respondeu. Veja $WEBLog" }
    else { Write-OK "Web no ar (http://localhost:$WEB_PORT)" }
}

function Stop-Web {
    $pids = Get-ListeningPids $WEB_PORT
    foreach ($pid_ in $pids) { Stop-Process -Id $pid_ -Force -ErrorAction SilentlyContinue }
    if ($pids.Count -gt 0) { Write-OK "Web parada." } else { Write-Info "Web não estava rodando." }
}

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
function Show-Status {
    Write-Host ""
    Write-Host "=== Status dos serviços ===" -ForegroundColor Cyan
    if (Test-ExternalPg) { Write-Host "PostgreSQL:  [OK] 127.0.0.1:5432 (externo)" -ForegroundColor Green }
    elseif (Test-EmbeddedPgUp) { Write-Host "PostgreSQL:  [OK] 127.0.0.1:5432 (embarcado)" -ForegroundColor Green }
    else { Write-Host "PostgreSQL:  [X] parado" -ForegroundColor Red }
    if (Test-ApiRunning) { Write-Host "API:         [OK] http://localhost:$API_PORT" -ForegroundColor Green }
    else { Write-Host "API:         [X] parada" -ForegroundColor Red }
    if (Test-WebRunning) { Write-Host "Web:         [OK] http://localhost:$WEB_PORT" -ForegroundColor Green }
    else { Write-Host "Web:         [X] parada" -ForegroundColor Red }
    Write-Host ""
}

# ---------------------------------------------------------------------------
# Ações
# ---------------------------------------------------------------------------
switch ($Action.ToLower()) {
    'start' {
        Write-Host ""; Write-Host "=== Iniciando Prospect.ai ===" -ForegroundColor Cyan; Write-Host ""
        Start-Postgres
        Start-Sleep -Seconds 1
        Invoke-DbMigrate
        Start-Api
        Start-Web
        Show-Status
        Write-Host "Logs: API=$APILog  Web=$WEBLog" -ForegroundColor Gray
    }
    'stop' {
        Write-Host ""; Write-Host "=== Parando Prospect.ai ===" -ForegroundColor Cyan; Write-Host ""
        Stop-Web
        Stop-Api
        Stop-Postgres
        Write-Host ""
    }
    'status' { Show-Status }
    'restart' {
        & $PSScriptRoot\dev.ps1 stop
        Start-Sleep -Seconds 2
        & $PSScriptRoot\dev.ps1 start
    }
    default {
        Write-Host ""
        Write-Host "Uso: .\scripts\dev.ps1 {start|stop|status|restart}" -ForegroundColor Yellow
        Write-Host ""
    }
}
