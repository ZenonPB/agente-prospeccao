# Prospect.ai — inteligência comercial e CRM B2B

Plataforma multi-workspace de prospecção, qualificação, inteligência comercial e
CRM. O primeiro release candidate é orientado à operação da AlphaMec, mas o
motor permanece genérico por meio de `OfferProfile`.

[![CI](https://github.com/ZenonPB/agente-prospeccao/actions/workflows/ci.yml/badge.svg)](https://github.com/ZenonPB/agente-prospeccao/actions/workflows/ci.yml)

## Estado do projeto

Em 2026-09-13, a `main` já contém:

- multi-workspace com papéis administrativos/comerciais e escopo de carteira;
- Unified Data Network com discovery/provider federation, provenance e quotas;
- Company e Person canônicas + entity resolution;
- campanhas, pre-scoring, enrichment, scoring e OfferMatcher;
- oportunidades por oferta, snapshots e attribution de outcomes;
- descoberta/verificação de decisores e roteabilidade;
- Next Best Action, sequences, workflows e tarefas;
- Kanban comercial, feedback útil/não útil e score feedback;
- CRM adapters/sync (Pipedrive, HubSpot e Salesforce);
- analytics/BI operacional;
- Controlled Learning com aprovação, publicação versionada e rollback;
- Opportunity 360 read-only.

O PR #172 está consolidando o uso do **OfferProfile efetivo por workspace** em
todo job do pipeline e adicionando Company 360/Person 360 read-only. O status
canônico fica em [`docs/00-status-mapa.md`](docs/00-status-mapa.md).

## Arquitetura

```text
Next.js Web
   ↓ JWT + X-Organization-Id
FastAPI API
   ├─ Campaigns / CRM / Analytics / Search
   ├─ Opportunity / Company / Person 360
   └─ Job consumer / WebSocket progress
          ↓
PostgreSQL 16
          ↑
Workers / Domain
   ├─ provider federation + entity resolution
   ├─ pre-scoring + enrichment
   ├─ scoring + OfferMatcher
   ├─ decision makers + next best action
   ├─ sequences / workflows / tasks
   └─ outcomes / analytics / controlled learning
```

Detalhes: [`docs/architecture.md`](docs/architecture.md).

## Modelo de domínio

- **Organization**: workspace/tenant.
- **Company**: conta canônica.
- **Person**: pessoa/decisor canônico.
- **Lead**: contexto comercial de uma conta em campanha/carteira.
- **LeadOpportunity**: oferta específica que pode ser vendida ao lead.
- **CommercialTask**: tarefa.
- **LeadActivity**: trilha comercial/auditoria.
- **CommercialOutcome**: resultado real atribuído.
- **OfferProfile / OfferProfileVersion**: configuração declarativa/versionada da oferta.

Uma empresa pode ter múltiplas oportunidades simultâneas. Outcome e learning
precisam preservar a oferta/versão corretas.

## Princípios

### Multi-workspace por construção

`organization_id` é boundary de autorização. Não basta esconder dado na UI:
backend, relações, providers, secrets, quotas, analytics, OfferProfiles e jobs
são tenant-safe e possuem testes cross-workspace.

### OfferProfile em vez de hardcode

ICP, sinais, thresholds, providers, enrichment, buyer persona, timing e lógica
específica da oferta são declarativos. O núcleo não ganha `if offer == ...` para
cada novo serviço.

### Human-in-the-loop

Feedback e outcomes alimentam análise. Mudanças de produção passam por
comparação/evidência, aprovação humana, publicação versionada e rollback.

### Evidência explicável

`UNKNOWN != FALSE`. FACT, INFERENCE e HYPOTHESIS permanecem distintos. Scores e
recomendações devem ser rastreáveis a sinais/evidências.

## Stack

| Camada | Tecnologias |
|---|---|
| API | Python, FastAPI, SQLAlchemy, JWT |
| Workers | Python, httpx, adapters/providers, OfferProfile engine |
| Banco | PostgreSQL 16 + Alembic |
| Web | Next.js, React, TypeScript, Tailwind, React Query |
| Testes | Pytest + PostgreSQL real em gates críticos |
| CI | GitHub Actions: backend, migrations, E2E e web |

As versões exatas são definidas pelos manifests/lockfiles, não por este README.

## Início rápido

### Pré-requisitos

- Python compatível com os requirements do repositório;
- Node.js compatível com `apps/web/package.json`/lockfile;
- PostgreSQL 16 ou Docker;
- `.env` baseado em `.env.example`.

### Docker para o banco

```bash
cp .env.example .env
docker compose up -d db
```

### Workers/migrations

```bash
cd services/workers
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python -m src.seeds.scoring_templates
```

### API

```bash
cd services/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Web

```bash
cd apps/web
npm ci
npm run dev
```

Para o fluxo automatizado/local completo, consulte [`QUICKSTART.md`](QUICKSTART.md).
Para produção, consulte [`DEPLOY.md`](DEPLOY.md).

## Configuração externa

Providers podem precisar de chaves como Google/Groq/Hunter, conforme a
capability habilitada. Em produção, secrets por workspace e providers externos
seguem opt-in/quota. Veja `.env.example` para o contrato atual — não copie uma
lista de variáveis de documentação antiga como fonte de verdade.

## Testes e gates

```bash
python -m compileall -q services/api services/workers
python -m pytest tests -q -W error

cd apps/web
npm ci
npm run lint
npx tsc --noEmit
npm run build
```

O CI também executa migrations em PostgreSQL real, segunda execução idempotente,
schema verifier e E2E/invariantes críticas. Um PR só é mergeado quando **todos
os checks do mesmo HEAD** estão verdes.

## Roadmap atual

Sequência do AlphaMec RC:

1. OfferProfile efetivo por workspace + Company/Person 360;
2. Opportunity 360 editável;
3. importador histórico seguro da planilha;
4. Filter Context + BI interativo;
5. coaching e calibração controlada;
6. Golden Path troféus/eventos/MEJ;
7. UAT multi-workspace;
8. campanha real autorizada + hardening final.

Veja [`docs/roadmap.md`](docs/roadmap.md) e
[`docs/pendencias-pos-consolidacao.md`](docs/pendencias-pos-consolidacao.md).

## Documentação

A pasta [`docs/`](docs/) possui uma hierarquia explícita:

- **LIVE**: estado atual;
- **RUNBOOK**: procedimentos operacionais;
- **ADR/DECISÃO**: decisões arquiteturais;
- **SNAPSHOT HISTÓRICO**: registro de fases antigas, não fonte de verdade atual.

Comece por [`docs/README.md`](docs/README.md).

## Segurança e privacidade

- não comitar secrets;
- evitar PII em logs;
- usar apenas métodos de coleta/enriquecimento permitidos pelos providers e
  pela política da organização;
- respeitar opt-out/suppression;
- revisar LGPD/retention antes do rollout real;
- automação externa deve ser auditável e explicitamente habilitada.

## Licença

MIT — veja [`LICENSE`](LICENSE).
