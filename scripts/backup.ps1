# ============================================================================
# backup.ps1 — Backup do PostgreSQL no Windows (paridade com backup.sh).
#
# Uso (PowerShell):
#   .\scripts\backup.ps1                       # backup em .\backups
#   .\scripts\backup.ps1 -RetentionDays 7      # apaga dumps com mais de 7 dias
#   .\scripts\backup.ps1 -VerifyRestore        # restaura o último dump em um
#                                              # banco temporário e valida
#
# A conexão vem de $env:DATABASE_URL ou, na falta dela, do `.env` da raiz.
# O pg_dump é procurado em: PATH → C:\Program Files\PostgreSQL\*\bin →
# Postgres embarcado do setup ($HOME\.local\agente-prospeccao\pgsql\bin).
# ============================================================================

param(
    [string]$BackupDir = "",
    [int]$RetentionDays = 14,
    [switch]$VerifyRestore
)

$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $BackupDir) { $BackupDir = Join-Path $RepoRoot "backups" }

function Write-OK   { param([string]$M) Write-Host "[OK] $M" -ForegroundColor Green }
function Write-Warn { param([string]$M) Write-Host "[AVISO] $M" -ForegroundColor Yellow }
function Write-Err  { param([string]$M) Write-Host "[ERRO] $M" -ForegroundColor Red }

# ---------------------------------------------------------------------------
# Conexão: $env:DATABASE_URL ou .env da raiz
# ---------------------------------------------------------------------------
if (-not $env:DATABASE_URL) {
    $envPath = Join-Path $RepoRoot ".env"
    if (Test-Path $envPath) {
        foreach ($line in Get-Content $envPath) {
            if ($line -match '^\s*DATABASE_URL\s*=\s*(.+)$') {
                $env:DATABASE_URL = $Matches[1].Trim()
                break
            }
        }
    }
}
if (-not $env:DATABASE_URL) {
    Write-Err "DATABASE_URL não definida (nem no ambiente, nem no .env da raiz)."
    exit 1
}

$uri = [System.Uri]$env:DATABASE_URL
$DbHost = $uri.Host
$DbPort = if ($uri.Port -gt 0) { $uri.Port } else { 5432 }
$DbUser = if ($uri.UserInfo) { [Uri]::UnescapeDataString(($uri.UserInfo -split ':')[0]) } else { "postgres" }
$DbPassword = if ($uri.UserInfo -and $uri.UserInfo.Contains(':')) {
    [Uri]::UnescapeDataString(($uri.UserInfo -split ':', 2)[1])
} else { "" }
$SrcDb = $uri.AbsolutePath.Trim('/')
if (-not $SrcDb) { Write-Err "DATABASE_URL sem nome de banco."; exit 1 }

if ($DbPassword) { $env:PGPASSWORD = $DbPassword } else { Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue }

# ---------------------------------------------------------------------------
# Localiza os clientes do PostgreSQL (pg_dump/pg_restore/psql)
# ---------------------------------------------------------------------------
function Find-PgTool {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @()
    $cands = Get-ChildItem "C:\Program Files\PostgreSQL\*\bin\$Name" -ErrorAction SilentlyContinue |
        Sort-Object {
            $v = $_.Directory.Parent.Name
            try { [version]$v } catch { try { [version]"$v.0" } catch { [version]"0.0" } }
        } -Descending
    if ($cands) { $candidates += $cands[0].FullName }
    $embedded = Join-Path $HOME ".local\agente-prospeccao\pgsql\bin\$Name"
    if (Test-Path $embedded) { $candidates += $embedded }
    if ($candidates.Count -gt 0) { return $candidates[0] }
    return $null
}

$PgDump = Find-PgTool "pg_dump.exe"
if (-not $PgDump) {
    Write-Err "pg_dump.exe não encontrado."
    Write-Err "Instale o PostgreSQL Client (ou o PostgreSQL completo) e/ou adicione o bin ao PATH."
    exit 1
}
Write-OK "pg_dump: $PgDump"

# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------
$Stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$DumpFile = Join-Path $BackupDir "prospeccao_$Stamp.dump"

# -f antes da URL de conexão (esta ordem é a aceita de forma estável).
& $PgDump --no-owner --format=custom -f $DumpFile $env:DATABASE_URL
if ($LASTEXITCODE -ne 0) { Write-Err "pg_dump falhou."; exit 1 }
Write-OK "Backup criado: $DumpFile ($([math]::Round((Get-Item $DumpFile).Length / 1KB)) KB)"

# Rotação
$cutoff = (Get-Date).AddDays(-$RetentionDays)
$old = Get-ChildItem $BackupDir -Filter "prospeccao_*.dump" -ErrorAction SilentlyContinue |
    Where-Object { $_.LastWriteTime -lt $cutoff }
foreach ($f in $old) { Remove-Item -Force $f.FullName }
if ($old.Count -gt 0) { Write-OK "Rotação: $($old.Count) dump(s) com mais de $RetentionDays dia(s) removido(s)." }

Write-Host ""
Write-Host "Restauração (exemplo):"
Write-Host "  pg_restore --clean --no-owner -d `$DATABASE_URL $DumpFile"

# ---------------------------------------------------------------------------
# Teste real de restore: restaura o dump mais recente em um banco temporário
# e compara a contagem de linhas das tabelas principais com a origem.
# ---------------------------------------------------------------------------
if ($VerifyRestore) {
    $PgRestore = Find-PgTool "pg_restore.exe"
    $Psql = Find-PgTool "psql.exe"
    if (-not $PgRestore -or -not $Psql) { Write-Err "pg_restore.exe/psql.exe não encontrados."; exit 1 }

    $latest = Get-ChildItem $BackupDir -Filter "prospeccao_*.dump" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $latest) { Write-Err "Nenhum dump encontrado em $BackupDir."; exit 1 }
    Write-Host "Verificando restore do dump: $($latest.FullName)"

    $TestDb = "prospeccao_restore_check"
    & $Psql -h $DbHost -p $DbPort -U $DbUser -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $TestDb;"
    if ($LASTEXITCODE -ne 0) { Write-Err "Falha ao preparar banco temporário."; exit 1 }
    & $Psql -h $DbHost -p $DbPort -U $DbUser -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $TestDb;"
    if ($LASTEXITCODE -ne 0) { Write-Err "Falha ao criar banco temporário."; exit 1 }

    $restoreUrl = "postgresql://$([Uri]::EscapeDataString($DbUser)):$([Uri]::EscapeDataString($DbPassword))@${DbHost}:$DbPort/$TestDb"
    & $PgRestore --no-owner --exit-on-error -d $restoreUrl $latest.FullName
    if ($LASTEXITCODE -ne 0) {
        & $Psql -h $DbHost -p $DbPort -U $DbUser -d postgres -c "DROP DATABASE IF EXISTS $TestDb;" | Out-Null
        Write-Err "Restore falhou — dump possivelmente corrompido."
        exit 1
    }

    # Lista principal do modelo atual; tabelas ausentes na origem são puladas.
    $tables = @(
        "organizations", "organization_members", "users", "campaigns",
        "campaign_scoring_templates", "leads", "contacts", "enrichments",
        "messages", "follow_ups", "conversions", "lead_activities",
        "provider_usage", "email_suppressions"
    )
    $fail = $false
    foreach ($t in $tables) {
        $exists = (& $Psql -h $DbHost -p $DbPort -U $DbUser -d $SrcDb -tAc "SELECT to_regclass('public.$t') IS NOT NULL") | Select-Object -Last 1
        if ("$exists".Trim() -ne "t") { continue }
        $src = (& $Psql -h $DbHost -p $DbPort -U $DbUser -d $SrcDb -tAc "SELECT count(*) FROM $t") | Select-Object -Last 1
        $dst = (& $Psql -h $DbHost -p $DbPort -U $DbUser -d $TestDb -tAc "SELECT count(*) FROM $t") | Select-Object -Last 1
        if ("$src".Trim() -ne "$dst".Trim()) {
            Write-Warn "$t : origem=$src restore=$dst"
            $fail = $true
        } else {
            Write-OK "$t : $src"
        }
    }

    & $Psql -h $DbHost -p $DbPort -U $DbUser -d postgres -c "DROP DATABASE IF EXISTS $TestDb;" | Out-Null

    if ($fail) { Write-Err "Restore não confere com a origem."; exit 1 }
    Write-OK "Restore validado ($($latest.Name))."
}
