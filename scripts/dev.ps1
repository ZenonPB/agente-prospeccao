# Script de desenvolvimento para Windows (PowerShell)
# Uso:
#   .\scripts\dev.ps1 start      # Inicia PostgreSQL (Docker), API e Web
#   .\scripts\dev.ps1 stop       # Para todos os serviços
#   .\scripts\dev.ps1 status     # Mostra status dos serviços

param(
    [Parameter(Position=0)]
    [ValidateSet('start', 'stop', 'status', 'restart')]
    [string]$Action = 'start'
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot

$API_PORT = if ($env:API_PORT) { $env:API_PORT } else { '8000' }
$WEB_PORT = if ($env:WEB_PORT) { $env:WEB_PORT } else { '3001' }

function Test-PostgresRunning {
    try {
        $result = docker ps --filter "name=agente-prospeccao-db" --filter "status=running" --quiet
        return -not [string]::IsNullOrEmpty($result)
    } catch {
        return $false
    }
}

function Test-ApiRunning {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$API_PORT/health" -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Test-WebRunning {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$WEB_PORT" -Method Get -TimeoutSec 2 -ErrorAction SilentlyContinue
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Start-Postgres {
    if (Test-PostgresRunning) {
        Write-Host "✓ PostgreSQL já está rodando" -ForegroundColor Green
        return
    }
    
    Write-Host "Iniciando PostgreSQL (Docker)..." -ForegroundColor Cyan
    Push-Location $RepoRoot
    try {
        docker-compose up -d db
        Start-Sleep -Seconds 3
        if (Test-PostgresRunning) {
            Write-Host "✓ PostgreSQL iniciado (localhost:5432)" -ForegroundColor Green
        } else {
            Write-Host "⚠ PostgreSQL não respondeu. Verifique 'docker-compose logs db'" -ForegroundColor Yellow
        }
    } finally {
        Pop-Location
    }
}

function Start-Api {
    if (Test-ApiRunning) {
        Write-Host "✓ API já está rodando" -ForegroundColor Green
        return
    }
    
    Write-Host "Iniciando API FastAPI..." -ForegroundColor Cyan
    $apiPath = Join-Path $RepoRoot "services\api"
    Push-Location $apiPath
    try {
        # Verifica se venv existe
        if (-not (Test-Path "venv\Scripts\activate.ps1")) {
            Write-Host "⚠ venv não encontrado. Criando..." -ForegroundColor Yellow
            python -m venv venv
            .\venv\Scripts\pip install -r requirements.txt
        }
        
        # Inicia API em background
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$apiPath'; .\venv\Scripts\activate; uvicorn main:app --host 0.0.0.0 --port $API_PORT" -WindowStyle Normal
        Start-Sleep -Seconds 3
        
        if (Test-ApiRunning) {
            Write-Host "✓ API iniciada em http://localhost:$API_PORT/docs" -ForegroundColor Green
        } else {
            Write-Host "⚠ API não respondeu. Verifique o terminal da API" -ForegroundColor Yellow
        }
    } finally {
        Pop-Location
    }
}

function Start-Web {
    if (Test-WebRunning) {
        Write-Host "✓ Web já está rodando" -ForegroundColor Green
        return
    }
    
    Write-Host "Iniciando Web (Next.js)..." -ForegroundColor Cyan
    $webPath = Join-Path $RepoRoot "apps\web"
    Push-Location $webPath
    try {
        # Verifica se node_modules existe
        if (-not (Test-Path "node_modules")) {
            Write-Host "⚠ node_modules não encontrado. Instalando dependências..." -ForegroundColor Yellow
            npm install
        }
        
        # Inicia Web em background
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$webPath'; npm run dev" -WindowStyle Normal
        Start-Sleep -Seconds 5
        
        if (Test-WebRunning) {
            Write-Host "✓ Web iniciada em http://localhost:$WEB_PORT" -ForegroundColor Green
        } else {
            Write-Host "⚠ Web não respondeu. Verifique o terminal da Web" -ForegroundColor Yellow
        }
    } finally {
        Pop-Location
    }
}

function Stop-Services {
    Write-Host "Parando serviços..." -ForegroundColor Cyan
    
    # Para Web (Node/Next)
    $webProcesses = Get-Process -Name node -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*agente-prospeccao*" }
    if ($webProcesses) {
        $webProcesses | Stop-Process -Force
        Write-Host "✓ Web parada" -ForegroundColor Green
    }
    
    # Para API (Python/uvicorn)
    $apiProcesses = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*uvicorn*" }
    if ($apiProcesses) {
        $apiProcesses | Stop-Process -Force
        Write-Host "✓ API parada" -ForegroundColor Green
    }
    
    # Para PostgreSQL (Docker)
    Push-Location $RepoRoot
    try {
        docker-compose stop db
        Write-Host "✓ PostgreSQL parado" -ForegroundColor Green
    } finally {
        Pop-Location
    }
}

function Show-Status {
    Write-Host "`n=== Status dos Serviços ===" -ForegroundColor Cyan
    
    if (Test-PostgresRunning) {
        Write-Host "PostgreSQL:  ✓ Rodando (localhost:5432)" -ForegroundColor Green
    } else {
        Write-Host "PostgreSQL:  ✗ Parado" -ForegroundColor Red
    }
    
    if (Test-ApiRunning) {
        Write-Host "API:         ✓ Rodando (http://localhost:$API_PORT)" -ForegroundColor Green
    } else {
        Write-Host "API:         ✗ Parada" -ForegroundColor Red
    }
    
    if (Test-WebRunning) {
        Write-Host "Web:         ✓ Rodando (http://localhost:$WEB_PORT)" -ForegroundColor Green
    } else {
        Write-Host "Web:         ✗ Parada" -ForegroundColor Red
    }
    
    Write-Host ""
}

# Executa ação solicitada
switch ($Action) {
    'start' {
        Write-Host "`n=== Iniciando Agente Prospecção ===" -ForegroundColor Cyan
        Start-Postgres
        Start-Sleep -Seconds 2
        Start-Api
        Start-Sleep -Seconds 2
        Start-Web
        Write-Host ""
        Show-Status
        Write-Host "Pressione Ctrl+C nas janelas abertas para parar os serviços" -ForegroundColor Yellow
    }
    'stop' {
        Write-Host "`n=== Parando Agente Prospecção ===" -ForegroundColor Cyan
        Stop-Services
        Write-Host ""
    }
    'status' {
        Show-Status
    }
    'restart' {
        Write-Host "`n=== Reiniciando Agente Prospecção ===" -ForegroundColor Cyan
        Stop-Services
        Start-Sleep -Seconds 3
        Start-Postgres
        Start-Sleep -Seconds 2
        Start-Api
        Start-Sleep -Seconds 2
        Start-Web
        Write-Host ""
        Show-Status
    }
}
