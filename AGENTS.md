# AGENTS.md

Guia compacto para sessões do OpenCode neste repositório. Todo o projeto
(`docs/`, UI, prompts) está em português — escreva código, mensagens e docs em
PT-BR salvo quando houver convenção contrária. Leia junto de `docs/` (ver
_Fluxo de trabalho_).

## O que é este projeto

**agente-prospeccao** — plataforma de **prospecção B2B** para a EJ (AlphaMec):
coleta, enriquecimento passivo, qualificação por IA e gestão de vendas de
leads. Três camadas que se comunicam via PostgreSQL + HTTP/WebSocket:

| Camada | Onde | Tecnologia |
|---|---|---|
| **Workers** | `services/workers/` | Python async (httpx), dono **único** dos modelos DB e migrations |
| **API** | `services/api/` | FastAPI REST + WS, JWT, multi-tenant, BI/PDF, scheduler de cadência |
| **Web** | `apps/web/` | Next.js 16 + React 19 + TS, shadcn/ui sobre `@base-ui/react` |

Pipeline: coleta (Google Places · CSV · CNAE) → enriquecimento adaptativo →
scoring contextual (Groq) → contatos (Receita/Hunter/busca passiva) → outreach
(cadência dia 0/3/7/14 + WhatsApp) → conversão → BI/PDF.

O estado vivo do sistema fica em `docs/context.md`. Leia primeiro.

## Fluxo de trabalho (sempre nesta ordem)

1. **Consulte o grafo de conhecimento primeiro** — `graphify query "<pergunta>"`
   responde antes de ler arquivos. Use `graphify path "A" "B"` para relações e
   `graphify explain "conceito"` para foco. Grafo em `graphify-out/graph.json`
   (gitignored); se ausente, gere com:
   `graphify extract . --code-only && graphify cluster-only . --no-label`.
   Após mudanças de código, rode `graphify update .` (AST-only, sem custo).
2. **Leia `docs/context.md`** — estado atual + "Próximo passo imediato".
3. **Carregue a skill apropriada ao momento** (seção _Skills_) antes de escrever
   código — não pule.
4. Leia `docs/architecture.md` e `docs/business-rules.md`; para o _porquê_,
   `docs/decisions.md` antes de propor mudanças; padrões de código em
   `docs/coding-standards.md`.
5. Confirme o entendimento da tarefa antes de escrever código.

## Skills (use a skill certa para o momento)

Skills são instruções especializadas carregadas com a ferramenta `skill`.
**Regra: para qualquer trabalho em frontend, carregue as skills de frontend
ANTES de escrever código.** Skills disponíveis nesta máquina:

### Frontend (`apps/web`)
| Skill | Quando usar |
|---|---|
| `frontend-design` | Criar/redesenhar UI: direção estética, tipografia, decisões visuais intencionais. **Sempre** em trabalho de UI novo ou refactor visual. |
| `vercel-react-best-practices` | Escrever/revisar/refatorar React/Next.js: performance, data fetching, bundle. **Sempre** em código React/Next. |
| `web-design-guidelines` | Auditar a UI existente contra boas práticas de web ("review my UI", acessibilidade, UX). |
| `tailwind` | Editar CSS/classes Tailwind v4 (projeto `hyperframes`); verificar v3 vs v4 antes de mexer em estilos. |

### Backend / qualidade
| Skill | Quando usar |
|---|---|
| `tdd` | Construir feature ou corrigir bug test-first (red-green-refactor) ou pedir testes/integração. |
| `improve-codebase-architecture` | Auditar/evoluir a arquitetura do código (gera relatório visual de aprofundamento). |

### Infra / automação / segurança
| Skill | Quando usar |
|---|---|
| `agent-browser` | Automatizar navegador: preencher formulários, clicar, screenshots, extrair dados, QA, testar a app web. |
| `firebase-security-rules-auditor` | Auditar regras de segurança Firebase — não se aplica a este repo (Postgres); ignorar. |
| `find-skills` | Procurar/instalar novas skills (`npx skills add <repo@skill> -g -y`). |
| `customize-opencode` | Apenas para configurar o próprio opencode (config, agents, skills, plugins) — não usar para código do app. |
| `setup-matt-pocock-skills` | Configuração única de issue tracker/vocabulário — não se aplica no dia a dia. |

### Graphify
| Skill | Quando usar |
|---|---|
| `/graphify` (skill instalada em `.opencode/skills/graphify/`) | Sempre que o usuário digitar `/graphify`, e como base de consulta do código (ver _graphify_ abaixo). |

## Environment & secrets

- `.env` (raiz) é **gitignored** e compartilhado pelos dois serviços Python via
  `env_file='../../.env'` relativo ao CWD. Nunca commitar ou ecoar valores —
  referencie config apenas por nome de env var.
- `JWT_SECRET` é obrigatório em `services/api/src/config/settings.py` — a API
  não sobe sem ele. Gerar com `openssl rand -hex 32`.
- `NEXTAUTH_SECRET` obrigatório em `apps/web/.env.local` (auto-login quebra sem
  ele). `NEXT_PUBLIC_API_URL` default `http://localhost:8000`.
- Chaves de IA: `GROQ_API_KEY`, `GOOGLE_API_KEY`, `HUNTER_API_KEY` (opcional),
  `SECRETS_ENCRYPTION_KEY`, `EMAIL_WEBHOOK_SECRET`, `TRACKING_BASE_URL`.
- **Pergunte antes de instalar dependências.**

## Estrutura

```
agente-prospeccao/
├── apps/web/                 ← Next.js 16 + React 19 (app router, shadcn/ui em @base-ui/react)
│   ├── src/app/(auth)/       ← login, register, esqueci/resetar-senha, aceitar-convite
│   ├── src/app/(protected)/  ← dashboard, campanhas(+nova,+[id]), oportunidades([id]),
│   │                            vendas(kanban), relatorios, configuracoes(+membros)
│   ├── src/components/       ← ui/(shadcn), layout/, páginas por feature
│   └── src/{lib,hooks,stores,types}/
├── services/
│   ├── api/                  ← FastAPI (main.py: app, CORS, rate limit, scheduler de cadência)
│   │   └── src/{config,auth,db,middleware,routes,services,pipeline_worker.py}
│   └── workers/              ← fonte única de models (src/database/models.py) e migrations
│       └── src/{config,database,seeds,services,scripts}
├── scripts/                  ← setup.sh/.ps1/.cmd · dev.sh/.ps1/.cmd · backup.sh
├── tests/                    ← pytest (unit, sem DB) — rodar da raiz
├── docs/                     ← documentação em PT (context/architecture/business-rules/decisions/coding-standards/agents/roadmap-*)
├── graphify-out/             ← grafo de conhecimento (gitignored; gerar se ausente)
└── .opencode/                ← config opencode (plugin/skills do graphify)
```

Modelos definidos **uma única vez** em `services/workers/src/database/models.py`;
a API re-exporta via `services/api/src/db/models.py` — nunca duplicar.

## Rodar

**API** (CWD `services/api` obrigatório — resolve `../../.env`):
```bash
uvicorn main:app --reload --port 8000   # http://localhost:8000/docs
```
- venv gitignored — criar se faltar: `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt`.
- Scheduler de cadência no lifespan (poll `CADENCE_POLL_SECONDS`, default 60s).
- CORS libera `http://localhost:3000` e `:3001`.

**Workers** (CWD `services/workers`):
```bash
source venv/bin/activate
python -m src.main                    # enriquecimento + scoring (limit=5)
python -m src.seeds.scoring_templates # seed idempotente dos templates
```
- `run_lead_collection(query, ...)` é função `async` separada — não via `python -m`.

**Frontend**:
```bash
cd apps/web && npm run dev            # http://localhost:3001
```

**Banco / Alembic** (CWD `services/workers`):
```bash
alembic upgrade head
alembic revision --autogenerate -m "..."
```
- Nunca editar migrations existentes — criar nova. Nunca dropar coluna em prod —
  marcar deprecated.
- Postgres + pgAdmin via `docker compose up -d` (db :5432, pgAdmin :5050).

**Windows sem Docker:** `scripts/setup.ps1` (setup idempotente, Postgres
embarcado zonky) e `scripts/dev.ps1 start|stop|status|restart` (ou `.cmd`).

## Testes & verificação

- `tests/` na raiz (pytest, unit-only). Instalar deps com
  `pip install -r requirements-dev.txt` e rodar **da raiz**:
  `python -m pytest tests -q`.
- `tests/conftest.py` injeta env vars dummy e conserta `sys.path`
  (`services.*|database.*|config.*` → workers; `src.*` → API). Não mover.
- CI (`.github/workflows/ci.yml`): web `npm run lint` → `npx tsc --noEmit` →
  `npm run build`; backend `python -m compileall -q services/api services/workers`
  + pytest; migrations job roda `alembic upgrade head` + seed smoke.
- Para verificação Python pontual não coberta por testes, rode o serviço direto.

## Convenções que importam

- **Tudo async** nos workers: `httpx.AsyncClient`, nunca `requests`, nunca
  função síncrona em serviço.
- **Filtros SQLAlchemy**: `&`/`|`, nunca `and`/`or` do Python.
- **Sem `print`** em serviços — usar `logging`.
- Um `XService` por arquivo em `src/services/`. Import cruzado é exceção:
  `enrichment_orchestrator.py` liga `technical_enrichment_service` +
  `scoring_service`; `contact_enrichment_service` importa `cnpj_service` de forma
  lazy. Nova orquestração vai lá ou em `main.py`, não em serviço irmão.
- Toda config via `src/config/settings.py` (pydantic-settings). Nunca ler
  `os.environ` diretamente.
- Frontend: shadcn/ui com `@base-ui/react` — usar a prop `render`, não `asChild`.
- `apps/web/AGENTS.md` tem regras próprias do Next 16 (breaking changes) — ler
  antes de editar aquele pacote.
- Nunca inventar APIs/endpoints — consultar docs reais.

## Scoring / regras de negócio

- Score 0–100; `>= 60` → `QUALIFICADO` (entra no outreach), `< 60` →
  `DESQUALIFICADO`.
- Funil: `NOVO → ANALISADO → QUALIFICADO/DESQUALIFICADO → CONTATADO → RESPONDIDO
  → REUNIAO_MARCADA → REUNIAO_FEITA → PROPOSTA_ENVIADA` (ou `PERDIDO`).
- **Lead sem site**: pula enriquecimento técnico mas **ainda é pontuado** pelo
  caminho business (em campanha de presença web é público-alvo — nunca
  desqualificar só por não ter site). Falha do Groq → permanece `NOVO`.
- `PERDIDO` por ausência de resposta re-entra na fila após `LOST_REQUEUE_DAYS`
  (default 90; perdas deliberadas `PRECO/CONCORRENTE/PRAZO/OUTRO` não voltam);
  cadência encerrada sem resposta vira `PERDIDO`/`NAO_RESPONDEU` após carência.
- **Toda análise de site é passiva** — nunca sondar, injetar, testar auth ou
  tomar ação não-passiva (Lei 12.737/2012).

## graphify

Projeto tem grafo de conhecimento em `graphify-out/` (god nodes, comunidades,
relações entre arquivos). A skill `/graphify` está instalada em
`.opencode/skills/graphify/` e um plugin registra `graphify update` automático.

**Regras:**
- Para perguntas sobre o código, rode **sempre** `graphify query "<pergunta>"`
  primeiro quando `graphify-out/graph.json` existir. Use `graphify path "A" "B"`
  (relações) e `graphify explain "conceito"` (foco). Retornam subgrafo escopado,
  bem menor que grep ou `GRAPH_REPORT.md`.
- Arquivos sujos em `graphify-out/` são esperados após hooks/updates
  incrementais — não é motivo para pular o graphify. Só pule se a tarefa for
  sobre saída do grafo errada/desatualizada, ou se o usuário mandar não usar.
- Se `graphify-out/wiki/index.md` existir, use-o para navegação ampla em vez de
  varrer o código.
- `graphify-out/GRAPH_REPORT.md` só para revisão de arquitetura ampla ou quando
  query/path/explain não bastarem.
- Após modificar código, rode `graphify update .` para manter o grafo atual
  (AST-only, sem custo de API).
- CLI instalada em `/tmp/opencode/graphify-venv/bin/graphify` (recriar com
  `python -m venv /tmp/opencode/graphify-venv && .../bin/pip install graphifyy`
  se sumir).
