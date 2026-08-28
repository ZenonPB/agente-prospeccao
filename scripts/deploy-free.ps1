# Deploy Gratuito - Prospect.ai (Windows)
# Uso: .\scripts\deploy-free.ps1 -DatabaseUrl "postgresql://user:pass@host/db"

param(
    [Parameter(Mandatory=$true)]
    [string]$DatabaseUrl
)

Write-Host "🚀 Prospect.ai - Deploy Gratuito" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Verificar pré-requisitos
Write-Host ""
Write-Host "📋 Pré-requisitos:" -ForegroundColor Yellow
Write-Host "  1. Conta no Render (gratuita)"
Write-Host "  2. Conta no Vercel (gratuita)"
Write-Host "  3. Conta no Neon (gratuita)"
Write-Host "  4. Git instalado"
Write-Host "  5. Node.js 20+ instalado"

# Gerar segredos
Write-Host ""
Write-Host "🔐 Gerando segredos..." -ForegroundColor Yellow

$JWT_SECRET = -join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) })
$NEXTAUTH_SECRET = [Convert]::ToBase64String((1..32 | ForEach-Object { Get-Random -Maximum 256 }))

Write-Host ""
Write-Host "📝 Variáveis de ambiente para o Render:" -ForegroundColor Green
Write-Host "========================================"
Write-Host ""
Write-Host "DATABASE_URL=$DatabaseUrl"
Write-Host "JWT_SECRET=$JWT_SECRET"
Write-Host "ENVIRONMENT=production"
Write-Host "SECRETS_ENCRYPTION_KEY=<gere_manualmente>"
Write-Host "NEXTAUTH_SECRET=$NEXTAUTH_SECRET"
Write-Host "GROQ_API_KEY=<sua_chave>"
Write-Host "GOOGLE_API_KEY=<sua_chave>"

Write-Host ""
Write-Host "📝 Variáveis de ambiente para o Vercel:" -ForegroundColor Green
Write-Host "========================================"
Write-Host ""
Write-Host "NEXT_PUBLIC_API_URL=<url_do_render>"
Write-Host "NEXTAUTH_SECRET=$NEXTAUTH_SECRET"

Write-Host ""
Write-Host "🔧 Próximos passos:" -ForegroundColor Yellow
Write-Host "==================="
Write-Host ""
Write-Host "1. Acesse https://render.com → New → Web Service"
Write-Host "   - Conecte o GitHub"
Write-Host "   - Build Command:"
Write-Host "     cd services/workers && pip install -r requirements.txt && cd ../api && pip install -r requirements.txt && cd ../../services/workers && alembic upgrade head"
Write-Host "   - Start Command:"
Write-Host "     cd services/api && uvicorn main:app --host 0.0.0.0 --port $`PORT"
Write-Host "   - Adicione as variáveis do Render acima"
Write-Host ""
Write-Host "2. Acesse https://vercel.com → New Project"
Write-Host "   - Importe o repositório"
Write-Host "   - Root Directory: apps/web"
Write-Host "   - Adicione as variáveis do Vercel acima"
Write-Host ""
Write-Host "3. Após deploy, atualize CORS_ORIGINS no Render com a URL do Vercel"
Write-Host ""
Write-Host "✅ Deploy concluído!" -ForegroundColor Green
Write-Host ""
Write-Host "📚 Documentação completa: DEPLOY.md"
