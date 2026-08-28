#!/bin/bash
# Build script para Render
set -e

echo "🔧 Building Prospect.ai API..."

# Instalar dependências dos workers
echo "📦 Instalando dependências dos workers..."
cd services/workers
pip install -r requirements.txt

# Instalar dependências da API
echo "📦 Instalando dependências da API..."
cd ../api
pip install -r requirements.txt

# Aplicar migrations
echo "🗄️ Aplicando migrations..."
cd ../workers
alembic upgrade head

echo "✅ Build concluído!"
