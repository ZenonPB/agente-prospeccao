# Quickstart — Prospect.ai

> Atualizado em 2026-09-13. `.env.example`, manifests e scripts do repositório
> têm precedência sobre exemplos deste guia.

## Caminho recomendado: scripts do projeto

### Windows

Primeiro setup:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

Depois:

```powershell
.\scripts\dev.ps1 start
.\scripts\dev.ps1 status
# .\scripts\dev.ps1 restart
# .\scripts\dev.ps1 stop
```

Também existem wrappers `.cmd` para uso por duplo clique quando presentes no
checkout.

### Linux/macOS

```bash
./scripts/setup.sh
./scripts/dev.sh start
./scripts/dev.sh status
# ./scripts/dev.sh restart
# ./scripts/dev.sh stop
```

Os scripts são a referência para portas, Postgres local/embarcado, migrations,
seed e processos de desenvolvimento. Não duplique manualmente configuração se
o script já a gerencia.

## Caminho manual

### 1. Ambiente

```bash
cp .env.example .env
```

Preencha somente as credenciais necessárias às capabilities que pretende usar.
Secrets reais não devem ser commitados.

### 2. PostgreSQL

Com Docker:

```bash
docker compose up -d db
```

Ou aponte `DATABASE_URL` para PostgreSQL 16 compatível.

### 3. Workers e migrations

```bash
cd services/workers
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python -m src.seeds.scoring_templates
```

### 4. API

Em outro terminal:

```bash
cd services/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Em ambiente não-production, a documentação OpenAPI fica disponível em
`http://localhost:8000/docs`.

### 5. Frontend

```bash
cd apps/web
npm ci
npm run dev
```

Confirme a URL exibida pelo Next.js/script local. O frontend precisa apontar
`NEXT_PUBLIC_API_URL` para a API local.

## Primeiro uso

1. crie um usuário;
2. confirme o workspace ativo;
3. configure providers/secrets necessários em Configurações;
4. crie uma campanha;
5. execute uma coleta pequena antes de aumentar volume;
6. acompanhe jobs/erros e verifique as oportunidades geradas.

Providers externos podem exigir opt-in, quota e credenciais por workspace.

## Testar antes de abrir PR

Na raiz:

```bash
python -m compileall -q services/api services/workers
python -m pytest tests -q -W error
```

Frontend:

```bash
cd apps/web
npm ci
npm run lint
npx tsc --noEmit
npm run build
```

O GitHub Actions adiciona gates de PostgreSQL real, migrations e E2E.

## Problemas comuns

### Migration pendente

```bash
cd services/workers
alembic upgrade head
```

Se houver divergência de schema, não crie coluna manualmente. Resolva pela cadeia
Alembic e pelo verifier do repositório.

### API não importa módulos

Verifique:
- venv correto;
- requirements instalados;
- comando executado a partir de `services/api` conforme scripts do projeto;
- `.env` carregável.

### Web não conecta à API

Verifique `NEXT_PUBLIC_API_URL`, API ativa, CORS local e workspace/session.

### Provider falha

Verifique secret/opt-in/quota **do workspace ativo**. Não assuma que uma chave
global substitui configuração tenant-specific em produção.

### Job parece parado

Consulte status persistido do job/logs antes de reiniciar processos. O pipeline
é consumido em background e possui recuperação para jobs stale; não rode a
mesma operação repetidamente sem verificar idempotência.

## Documentação seguinte

- arquitetura: `docs/architecture.md`;
- estado: `docs/00-status-mapa.md`;
- roadmap: `docs/roadmap.md`;
- baseline/gates: `docs/baseline-operacional.md`;
- deploy: `DEPLOY.md`.
