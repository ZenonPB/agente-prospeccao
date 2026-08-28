# Deploy Gratuito - Prospect.ai

## Arquitetura de Deploy

```
┌─────────────────────────────────────────────────────────────┐
│                     USUÁRIO (Browser)                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  VERCEL (Frontend Next.js)                                  │
│  • Domínio: prospect.vercel.app                             │
│  • SSL automático                                           │
│  • Build: npm run build                                     │
└─────────────────────────┬───────────────────────────────────┘
                          │ API calls
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  RENDER (Backend FastAPI + Workers)                         │
│  • URL: prospect-api.onrender.com                           │
│  • Porta: 8000 (automática)                                 │
│  • Workers: enriquecimento/scoring em background             │
└─────────────────────────┬───────────────────────────────────┘
                          │ queries
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  NEON (PostgreSQL)                                          │
│  • URL: ep-xxx.us-east-2.aws.neon.tech                      │
│  • 0.5 GB gratuito permanente                               │
│  • Scale-to-zero (economia)                                 │
└─────────────────────────────────────────────────────────────┘
```

## Passo 1: Banco de Dados (Neon)

1. Acesse [neon.com](https://neon.com) → Criar conta grátis
2. Criar novo projeto:
   - Nome: `prospect-db`
   - Region: `US East (Ohio)` ou mais próxima
3. Copiar a `DATABASE_URL` (formato: `postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/prospect`)
4. Salvar em local seguro

## Passo 2: Backend (Render)

### Opção A: Deploy Manual

1. Acesse [render.com](https://render.com) → Criar conta grátis
2. **New** → **Web Service**
3. Conectar repositório GitHub
4. Configurar:
   - **Name**: `prospect-api`
   - **Runtime**: Python
   - **Build Command**:
     ```bash
     cd services/workers && pip install -r requirements.txt && cd ../api && pip install -r requirements.txt && cd ../../services/workers && alembic upgrade head
     ```
   - **Start Command**:
     ```bash
     cd services/api && uvicorn main:app --host 0.0.0.0 --port $PORT
     ```
   - **Plan**: Free

5. Adicionar variáveis de ambiente:
   ```
   DATABASE_URL=<cole_do_neon>
   JWT_SECRET=<gere_com: openssl rand -hex 32>
   ENVIRONMENT=production
   GROQ_API_KEY=<sua_chave>
   GOOGLE_API_KEY=<sua_chave>
   SECRETS_ENCRYPTION_KEY=<gere_com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
   NEXTAUTH_SECRET=<gere_com: openssl rand -base64 32>
   ```

6. **Create Web Service**

### Opção B: Blueprint (render.yaml)

```bash
# Instalar Render CLI
npm install -g render-sh

# Deploy via Blueprint
render blueprint apply
```

## Passo 3: Frontend (Vercel)

1. Acesse [vercel.com](https://vercel.com) → Criar conta com GitHub
2. **New Project** → Importar repositório
3. Configurar:
   - **Framework Preset**: Next.js
   - **Root Directory**: `apps/web`
   - **Build Command**: `npm run build`
   - **Output Directory**: `.next`

4. Variáveis de ambiente:
   ```
   NEXT_PUBLIC_API_URL=https://prospect-api.onrender.com
   NEXTAUTH_SECRET=<mesmo_do_render>
   ```

5. **Deploy**

## Passo 4: Configuração Final

### 4.1 Atualizar CORS na API

No arquivo `services/api/src/config/settings.py`, adicione o domínio do Vercel:

```python
CORS_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://localhost:3001",
    "https://prospect.vercel.app",  # ← ADICIONAR
]
```

### 4.2 Configurar Tracking (Opcional)

Se quiser rastreamento de abertura/clique de e-mail:

```
TRACKING_BASE_URL=https://prospect-api.onrender.com
```

### 4.3 Configurar SMTP (Opcional para produção)

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu-email@gmail.com
SMTP_PASSWORD=sua-senha-de-app
SMTP_FROM_EMAIL=seu-email@gmail.com
SMTP_FROM_NAME=Prospect.ai
```

## Variáveis de Ambiente Completas

### Backend (Render)
```bash
# Banco de dados
DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/prospect

# Segurança
JWT_SECRET=abc123...  # openssl rand -hex 32
SECRETS_ENCRYPTION_KEY=xyz789...  # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
NEXTAUTH_SECRET=def456...  # openssl rand -base64 32

# APIs externas
GROQ_API_KEY=gsk_...
GOOGLE_API_KEY=AIza...

# Ambiente
ENVIRONMENT=production
CORS_ORIGINS=https://prospect.vercel.app

# Opcional
HUNTER_API_KEY=
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
TRACKING_BASE_URL=https://prospect-api.onrender.com
```

### Frontend (Vercel)
```bash
NEXT_PUBLIC_API_URL=https://prospect-api.onrender.com
NEXTAUTH_SECRET=def456...  # mesmo do backend
```

## Verificação Pós-Deploy

1. **API Health Check**:
   ```bash
   curl https://prospect-api.onrender.com/health
   ```

2. **Frontend**:
   - Acessar `https://seu-app.vercel.app`
   - Criar conta
   - Testar criação de campanha

3. **Logs**:
   - Render: Dashboard → prospect-api → Logs
   - Vercel: Dashboard → projeto → Logs

## Limitações do Plano Gratuito

| Serviço | Limite | Impacto |
|---------|--------|---------|
| **Render** | 750 horas/mês | ~31 dias rodando 24/7 |
| **Render** | 512 MB RAM | Suficiente para API leve |
| **Render** | Cold start 30-60s | Primeira request após inatividade |
| **Neon** | 0.5 GB storage | ~500.000 leads |
| **Neon** | 100 CU-hours/mês | Compute suspenso após 5 min idle |
| **Vercel** | Ilimitado | Sem restrições significativas |

## Troubleshooting

### Erro: "Exited with status 1 while building"

**Causa provável**: Erro no build do Dockerfile ou dependências faltando.

**Solução**:

1. **Verificar logs do build**:
   - Render Dashboard → prospect-api → Logs
   - Procure por erros de `pip install` ou `apt-get`

2. **Se o erro for no WeasyPrint**:
   - O Render pode não ter as dependências de sistema
   - Usar `Dockerfile.render` (sem WeasyPrint) - já configurado

3. **Se o erro for nas migrations**:
   - Verificar se `DATABASE_URL` está correto
   - Neon: adicionar `?sslmode=require` na URL

4. **Build manual para teste**:
   ```bash
   # Testar localmente
   docker build -f services/api/Dockerfile.render -t prospect-api .
   docker run -e DATABASE_URL=sua_url prospect-api
   ```

### Erro: "JWT_SESSION_ERROR"
- Verificar se `NEXTAUTH_SECRET` está definido no Vercel
- Regenerar: `openssl rand -base64 32`

### Erro: "DATABASE_URL invalid"
- Verificar formatação: `postgresql://user:pass@host/db`
- Neon: usar SSL? Adicionar `?sslmode=require`

### Cold start muito lento
- Render free: normal (30-60s)
- Solução: upgrade para Basic ($7/mês) ou usar Railway ($5/mês)

### Workers não estão rodando
- Workers rodam como processo separado no mesmo service
- Verificar logs: Render → prospect-api → Logs

### Erro: "permission denied" no build
- O Render pode precisar de permissão de execução
- Solução: usar Dockerfile ao invés de build command
