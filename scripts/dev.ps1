# Script de desenvolvimento para Windows (PowerShell)
# Uso:
#   .\scripts\dev.ps1 start      # Inicia PostgreSQL (Docker), API e Web
#   .\scripts\dev.ps1 stop       # Para todos os serviços
#   .\scripts\dev.ps1 status     # Mostra status dos serviços

param(
    [Parameter(Position=0)]
    [string]$Action = 'start'
)

$ErrorActionPreference = 'Continue'
$RepoRoot = Split-Path -Parent $PSScriptRoot

$API_PORT = '8000'
$WEB_PORT = '3001'

if ($env:API_PORT) {
    $API_PORT = $env:API_PORT
}
if ($env:WEB_PORT) {
    $WEB_PORT = $env:WEB_PORT
}

function Test-PostgresRunning {
    try {
        $service = Get-Service -Name "*postgres*" -ErrorAction SilentlyContinue
        return $service -and $service.Status -eq 'Running'
    }
    catch {
        return $false
    }
}

function Test-ApiRunning {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$API_PORT/health" -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

function Test-WebRunning {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$WEB_PORT" -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

function Start-Postgres {
    if (Test-PostgresRunning) {
        Write-Host "[OK] PostgreSQL ja esta rodando (Servico do Windows)" -ForegroundColor Green
        return
    }
    
    Write-Host "Iniciando Servico do PostgreSQL..." -ForegroundColor Cyan
    Start-Service -Name "postgresql-x64-16" -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    
    if (Test-PostgresRunning) {
        Write-Host "[OK] PostgreSQL iniciado (localhost:5432)" -ForegroundColor Green
    }
    else {
        Write-Host "[AVISO] PostgreSQL nao respondeu. Verifique os Servicos do Windows" -ForegroundColor Yellow
    }
}

function Start-Api {
    if (Test-ApiRunning) {
        Write-Host "[OK] API já está rodando" -ForegroundColor Green
        return
    }
    
    Write-Host "Iniciando API FastAPI..." -ForegroundColor Cyan
    $apiPath = Join-Path $RepoRoot "services\api"
    
    if (!(Test-Path "$apiPath\venv")) {
        Write-Host "Criando venv para API..." -ForegroundColor Yellow
        Set-Location $apiPath
        python -m venv venv
        & "$apiPath\venv\Scripts\pip.exe" install -r requirements.txt
    }
    
    $startCmd = "Set-Location '$apiPath'; & '$apiPath\venv\Scripts\activate.ps1'; uvicorn main:app --host 0.0.0.0 --port $API_PORT"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $startCmd
    Start-Sleep -Seconds 3
    
    if (Test-ApiRunning) {
        Write-Host "[OK] API iniciada em http://localhost:$API_PORT/docs" -ForegroundColor Green
    }
    else {
        Write-Host "[AVISO] API não respondeu. Verifique o terminal da API" -ForegroundColor Yellow
    }
}

function Start-Web {
    if (Test-WebRunning) {
        Write-Host "[OK] Web já está rodando" -ForegroundColor Green
        return
    }
    
    Write-Host "Iniciando Web (Next.js)..." -ForegroundColor Cyan
    $webPath = Join-Path $RepoRoot "apps\web"
    
    if (!(Test-Path "$webPath\node_modules")) {
        Write-Host "Instalando dependências do Web..." -ForegroundColor Yellow
        Set-Location $webPath
        npm install
    }
    
    $startCmd = "Set-Location '$webPath'; npm run dev"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $startCmd
    Start-Sleep -Seconds 5
    
    if (Test-WebRunning) {
        Write-Host "[OK] Web iniciada em http://localhost:$WEB_PORT" -ForegroundColor Green
    }
    else {
        Write-Host "[AVISO] Web não respondeu. Verifique o terminal da Web" -ForegroundColor Yellow
    }
}

function Stop-Services {
    Write-Host "Parando serviços..." -ForegroundColor Cyan
    
    # Para Web (Node/Next)
    $webProcesses = Get-Process -Name node -ErrorAction SilentlyContinue
    if ($webProcesses) {
        $webProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] Web parada" -ForegroundColor Green
    }
    
    # Para API (Python/uvicorn)
    $apiProcesses = Get-Process -Name python -ErrorAction SilentlyContinue
    if ($apiProcesses) {
        $apiProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
        Write-Host "[OK] API parada" -ForegroundColor Green
    }
    
    # Para PostgreSQL (opcional)
    Write-Host "[INFO] Mantendo PostgreSQL rodando (Servico do Windows)" -ForegroundColor Gray
}

function Show-Status {
    Write-Host ""
    Write-Host "=== Status dos Servicos ===" -ForegroundColor Cyan
    Write-Host ""
    
    if (Test-PostgresRunning) {
        Write-Host "PostgreSQL:  [OK] Rodando (localhost:5432)" -ForegroundColor Green
    }
    else {
        Write-Host "PostgreSQL:  [X] Parado" -ForegroundColor Red
    }
    
    if (Test-ApiRunning) {
        Write-Host "API:         [OK] Rodando (http://localhost:$API_PORT)" -ForegroundColor Green
    }
    else {
        Write-Host "API:         [X] Parada" -ForegroundColor Red
    }
    
    if (Test-WebRunning) {
        Write-Host "Web:         [OK] Rodando (http://localhost:$WEB_PORT)" -ForegroundColor Green
    }
    else {
        Write-Host "Web:         [X] Parada" -ForegroundColor Red
    }
    
    Write-Host ""
}

# Executa ação solicitada
switch ($Action) {
    'start' {
        Write-Host ""
        Write-Host "=== Iniciando Agente Prospeccao ===" -ForegroundColor Cyan
        Write-Host ""
        Start-Postgres
        Start-Sleep -Seconds 2
        Start-Api
        Start-Sleep -Seconds 2
        Start-Web
        Show-Status
        Write-Host "Pressione Ctrl+C nas janelas abertas para parar os servicos" -ForegroundColor Yellow
        Write-Host ""
    }
    'stop' {
        Write-Host ""
        Write-Host "=== Parando Agente Prospeccao ===" -ForegroundColor Cyan
        Write-Host ""
        Stop-Services
        Write-Host ""
    }
    'status' {
        Show-Status
    }
    'restart' {
        Write-Host ""
        Write-Host "=== Reiniciando Agente Prospeccao ===" -ForegroundColor Cyan
        Write-Host ""
        Stop-Services
        Start-Sleep -Seconds 3
        Start-Postgres
        Start-Sleep -Seconds 2
        Start-Api
        Start-Sleep -Seconds 2
        Start-Web
        Show-Status
    }
    default {
        Write-Host ""
        Write-Host "Uso: .\scripts\dev.ps1 {start|stop|status|restart}" -ForegroundColor Yellow
        Write-Host ""
    }
}
