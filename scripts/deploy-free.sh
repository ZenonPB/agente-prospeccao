#!/bin/bash
# Deploy Gratuito - Prospect.ai
# Uso: ./scripts/deploy-free.sh [neon_url]

set -e

echo "🚀 Prospect.ai - Deploy Gratuito"
echo "================================"

# Verificar se a URL do Neon foi fornecida
if [ -z "$1" ]; then
    echo "❌ Uso: ./scripts/deploy-free.sh <DATABASE_URL>"
    echo "   Exemplo: ./scripts/deploy-free.sh postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/prospect"
    exit 1
fi

DATABASE_URL="$1"

echo ""
echo "📋 Pré-requisitos:"
echo "  1. Conta no Render (gratuita)"
echo "  2. Conta no Vercel (gratuita)"
echo "  3. Conta no Neon (gratuita)"
echo "  4. Git instalado"
echo "  5. Node.js 20+ instalado"
echo ""

# Gerar segredos
echo "🔐 Gerando segredos..."
JWT_SECRET=$(openssl rand -hex 32)
NEXTAUTH_SECRET=$(openssl rand -base64 32)
SECRETS_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || echo "")

if [ -z "$SECRETS_KEY" ]; then
    echo "⚠️  Não foi possível gerar SECRETS_ENCRYPTION_KEY automaticamente"
    echo "   Gere manualmente: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    SECRETS_KEY="<gere_manualmente>"
fi

echo ""
echo "📝 Variáveis de ambiente para o Render:"
echo "========================================"
echo ""
echo "DATABASE_URL=$DATABASE_URL"
echo "JWT_SECRET=$JWT_SECRET"
echo "ENVIRONMENT=production"
echo "SECRETS_ENCRYPTION_KEY=$SECRETS_KEY"
echo "NEXTAUTH_SECRET=$NEXTAUTH_SECRET"
echo "GROQ_API_KEY=<sua_chave>"
echo "GOOGLE_API_KEY=<sua_chave>"
echo ""
echo "📝 Variáveis de ambiente para o Vercel:"
echo "========================================"
echo ""
echo "NEXT_PUBLIC_API_URL=<url_do_render>"
echo "NEXTAUTH_SECRET=$NEXTAUTH_SECRET"
echo ""

echo "🔧 Próximos passos:"
echo "==================="
echo ""
echo "1. Acesse https://render.com → New → Web Service"
echo "   - Conecte o GitHub"
echo "   - Build Command:"
echo "     cd services/workers && pip install -r requirements.txt && cd ../api && pip install -r requirements.txt && cd ../../services/workers && alembic upgrade head"
echo "   - Start Command:"
echo "     cd services/api && uvicorn main:app --host 0.0.0.0 --port \$PORT"
echo "   - Adicione as variáveis do Render acima"
echo ""
echo "2. Acesse https://vercel.com → New Project"
echo "   - Importe o repositório"
echo "   - Root Directory: apps/web"
echo "   - Adicione as variáveis do Vercel acima"
echo ""
echo "3. Após deploy, atualize CORS_ORIGINS no Render com a URL do Vercel"
echo ""
echo "✅ Deploy concluído!"
echo ""
echo "📚 Documentação completa: DEPLOY.md"
