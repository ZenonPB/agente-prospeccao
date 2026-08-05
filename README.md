# Agente Prospecção

Plataforma de **prospecção B2B** para PMEs brasileiras que vendem serviços:
coleta de leads multi-fonte, enriquecimento passivo, qualificação com IA
explicável (score 0–100), outreach com cadência (humano no loop por padrão)
e relatórios de inteligência comercial.

```
Usuário/Org descreve a oferta → campanha (Places/CSV/CNAE)
        ↓
Coleta → enriquecimento adaptativo (site? CNPJ? contatos?)
        ↓
Score contextual explicável (templates + LLM) → prioridade HOT/WARM/COLD
        ↓
Atribuição ao consultor → mensagens IA → cadência dia 0/3/7/14 (LGPD/opt-out)
        ↓
Resultado real (ganhou/perdeu) → BI por analista → PDF para a diretoria
        ↓
Feedback converte-se em calibração do próximo ciclo
```

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic |
| Workers | httpx async · Google Places · Groq (LLM) · Receita/CNPJ |
| Banco | PostgreSQL |
| Frontend | Next.js 16 · React 19 · TypeScript · shadcn/ui (@base-ui/react) |
| BI/PDF | Analytics org-scoped · WeasyPrint |

## Estrutura

```
services/workers/  — modelos (fonte única), migrations, coleta/enriquecimento/scoring
services/api/      — API REST + WebSocket, scheduler de cadência, BI, PDF
apps/web/          — frontend (dashboard, campanhas, oportunidades, vendas, relatórios)
docs/              — documentação em português (context, architecture, auditoria, ...)
```

## Rodando em desenvolvimento

### Opção A — Windows (PowerShell)

Execute o script `scripts/dev.ps1` no PowerShell:

```powershell
.\scripts\dev.ps1 start    # Sobe PostgreSQL (Docker), API (:8000) e Web (:3001)
.\scripts\dev.ps1 status   # Verifica se tudo está rodando
.\scripts\dev.ps1 stop     # Para todos os serviços
```

Os arquivos `.env` (raiz do projeto) e `apps/web/.env.local` já foram configurados automaticamente com as suas chaves de API (`GROQ_API_KEY`, `GOOGLE_API_KEY`, `HUNTER_API_KEY`).

### Opção B — Linux/macOS (Script Bash)

1. Configure o ambiente:
   ```bash
   cp .env.example .env
   # preencha DATABASE_URL, JWT_SECRET, GROQ_API_KEY, GOOGLE_API_KEY, ...
   ```
2. Banco (opcional — se não tiver Postgres local):
   ```bash
   docker compose up -d db
   ```
3. Migrations:
   ```bash
   cd services/workers
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   alembic upgrade head
   ```
4. API:
   ```bash
   cd services/api
   source venv/bin/activate && pip install -r requirements.txt
   uvicorn main:app --reload --port 8000    # docs em http://localhost:8000/docs
   ```
5. Frontend:
   ```bash
   cd apps/web
   npm ci && npm run dev                    # http://localhost:3001
   ```

## Rodando em produção (Docker)

```bash
cp .env.example .env        # preencha todas as variáveis (JWT_SECRET obrigatório)
docker compose up -d --build
# API em :8000 · web em :3000 (WEB_PORT para mudar)
```

> Em produção, `ENVIRONMENT=production` **exige** SMTP configurado — envio de
> e-mail falha em vez de "fingir" que funcionou. Configure também
> `EMAIL_WEBHOOK_SECRET` para o inbound de respostas/STOP e
> `SECRETS_ENCRYPTION_KEY` para as chaves BYOK por org.

## Backup

O volume `db_backups` está montado em `/backups` no container do Postgres.
Cron sugerido (host):

```bash
docker compose exec db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -Fc -f /backups/$(date +%F).dump
```

## Docs

Toda a documentação está em `docs/` (português). Leia na ordem:
`context.md` (estado atual) → `architecture.md` → `business-rules.md`.
Consulte `decisions.md` antes de mudanças e `coding-standards.md`/`agents.md`
para convenções de código e dos agentes.
