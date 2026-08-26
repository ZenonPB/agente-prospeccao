<div align="center">

# 🎯 Prospect.ai

**Plataforma de prospecção B2B com IA para PMEs brasileiras que vendem serviços**

Coleta multi-fonte · Enriquecimento passivo · Qualificação com IA explicável · Outreach com cadência · BI comercial

[![CI](https://github.com/ZenonPB/agente-prospeccao/actions/workflows/ci.yml/badge.svg)](https://github.com/ZenonPB/agente-prospeccao/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=flat&logo=fastapi&logoColor=white)](https://www.fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-16-000000?style=flat&logo=next.js&logoColor=white)](https://nextjs.org/)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat)](LICENSE)

</div>

---

## 📖 Índice

- [Sobre o projeto](#-sobre-o-projeto)
- [Como funciona](#-como-funciona)
- [Funcionalidades](#-funcionalidades)
- [Stack tecnológica](#-stack-tecnológica)
- [Início rápido](#-início-rápido)
- [Variáveis de ambiente](#-variáveis-de-ambiente)
- [Estrutura do repositório](#-estrutura-do-repositório)
- [Testes e CI](#-testes-e-ci)
- [Backup e operação](#-backup-e-operação)
- [Solução de problemas](#️-solução-de-problemas)
- [Documentação](#-documentação)
- [Contribuindo](#-contribuindo)
- [Licença](#-licença)

---

## 📌 Sobre o projeto

O **Prospect.ai** automatiza o funil comercial de ponta a ponta para empresas que vendem serviços: encontra as empresas certas, descobre **quem** é o decisor, pontua a oportunidade com IA **explicável**, gera as mensagens de abordagem e acompanha cada negociação até o contrato — com BI executivo para a diretoria.

Tudo isso respeitando três princípios:

- **Análise 100% passiva** dos sites prospectados (Lei 12.737/2012) — nenhuma sondagem, injeção ou varredura agressiva.
- **Humano no loop por padrão** — o consultor revisa e envia; o automático é opt-in e tem freios (teto diário, janela, verificação).
- **Explicabilidade** — todo score vem com fatores (+/−), evidências e resumo executivo legível.

---

## ⚙️ Como funciona

```
Oferta descrita em linguagem natural ──► Campanha (wizard ou modo Agente)
        │
        ▼
COLETA  ◄── Google Places · CSV · CNAE/Receita · Licitações PNCP
        │
        ▼
ENRIQUECIMENTO ADAPTATIVO  ◄── site (técnico) · CNPJ (cadastral) · decisores (e-mail/LinkedIn)
        │
        ▼
SCORE CONTEXTUAL EXPLICÁVEL  ──► 0–100 + prioridade HOT/WARM/COLD
        │      (≥ 60 → QUALIFICADO · < 60 → DESQUALIFICADO)
        ▼
OUTREACH  ──► mensagens geradas por IA → cadência dia 0/3/7/14 (ou calendário da vertente)
        │      e-mail rastreado (abertura/clique) · WhatsApp 1 clique
        ▼
FUNIL COMERCIAL  ──► NOVO → CONTATADO → RESPONDIDO → REUNIÃO → PROPOSTA → GANHO/PERDIDO
        │
        ▼
BI EXECUTIVO  ──► dashboard · funil ponta-a-ponta · forecast · mapa · PDF para a diretoria
```

**Regra de negócio central:** leads qualificados (score ≥ 60) entram no outreach. Perdas por falta de resposta voltam à fila após 90 dias; perdas deliberadas (preço/concorrente/prazo) e opt-outs nunca voltam. Lead **sem site** não é descartado — em campanhas de presença web ele é exatamente o público-alvo.

---

## ✨ Funcionalidades

| Área | O que o sistema faz |
|---|---|
| **Campanhas** | Wizard em 4 passos ou **modo Agente** (brief em PT-BR vira campanha pronta para revisão); coleta incremental por rodada |
| **Fontes de leads** | Google Places, importação CSV (com detecção de layout de listas setoriais), busca por CNAE na Receita, contratos públicos do **PNCP** |
| **Vertentes de avaliação** | Templates de critérios por segmento (sites, SEO, ERPs, engenharia, personalizados…) — editáveis na UI, duplicáveis e **gerados por IA** a partir de uma descrição |
| **Enriquecimento** | Análise técnica passiva do site (CMS, SSL, SEO, UX, performance), dados cadastrais (CNPJ/CNAE/porte), reputação Google, sincronização opcional com Google Sheets (OAuth2) |
| **Decisores** | E-mail e LinkedIn do decisor via múltiplas fontes (Hunter, site, Receita, busca passiva) com badge de confiança e proveniência |
| **Outreach** | Sequência de mensagens por IA com pitch factual (anti-"texto genérico de IA"), cadência configurável por vertente, threading de e-mail, pixel de abertura e redirect de clique |
| **WhatsApp** | Botão 1 clique com texto pré-preenchido, validação de número BR e registro na trilha do lead |
| **Funil / Vendas** | Kanban drag-and-drop com SLA de leads parados, atribuição por consultor, negociação (RD/Orçamento/RP), registro de conversão e pós-venda |
| **BI & Relatórios** | KPIs executivos, funil ponta-a-ponta, desempenho por consultor (com metas), mapa de oportunidades, forecast ponderado e **PDF executivo** |
| **Multi-organização** | Workspaces isolados, convites por e-mail (com cadastro no aceite), papéis owner/admin + CONSULTOR/ANALYST/MANAGER, trilha de auditoria administrativa |
| **Confiabilidade** | Cotas por organização/provedor, monitor de entregabilidade (pausa envio se bounce > 5%), segredos BYOK criptografados, painel de webhooks/jobs |

---

## 🏗️ Stack tecnológica

| Camada | Tecnologias |
|---|---|
| **API** | Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic · JWT |
| **Workers / Integrações** | httpx async · Google Places · Groq (LLM) · Receita Federal / BrasilAPI · PNCP · Hunter (opcional) |
| **Banco de dados** | PostgreSQL 16 |
| **Frontend** | Next.js 16 · React 19 · TypeScript · Tailwind v4 · shadcn/ui sobre Base UI |
| **BI / Relatórios** | Analytics org-scoped · Recharts · Leaflet · WeasyPrint (PDF) |
| **Infra / DevOps** | Docker · Docker Compose · GitHub Actions · Postgres embarcado (dev Windows/Linux sem Docker) |
| **Testes** | Pytest (444+ testes unitários/E2E) |

---

## 🚀 Início rápido

### Pré-requisitos

- [Python 3.12+](https://www.python.org/downloads/) e [Node.js 20+](https://nodejs.org/)
- Chaves de API: `GROQ_API_KEY` (qualificação/mensagens) e `GOOGLE_API_KEY` (coleta Places) — `HUNTER_API_KEY` é opcional
- Docker **ou** nada (o fluxo recomendado usa PostgreSQL embarcado, sem instalar nada)

### 🪟 Opção A — Windows sem Docker (recomendada)

Um único comando idempotente faz tudo: baixa PostgreSQL embarcado, cria os venvs, gera `.env`/`.env.local` com segredos automáticos, aplica migrations, roda o seed e instala o frontend.

**Sem terminal (duplo clique):**

1. Duplo clique em **`scripts\setup.cmd`** — setup completo (uma única vez)
2. Duplo clique em **`scripts\dev.cmd`** — sobe tudo

**Via PowerShell:**

```powershell
.\scripts\setup.ps1              # setup idempotente (pode reexecutar à vontade)
.\scripts\dev.ps1 start          # Postgres + migrations + seed + API (:8000) + Web (:3001)
.\scripts\dev.ps1 status         # o que está rodando
.\scripts\dev.ps1 restart        # stop + start
.\scripts\dev.ps1 stop           # para tudo
```

> ✅ Única pendência manual: preencher `GROQ_API_KEY` e `GOOGLE_API_KEY` no `.env` da raiz e reiniciar (`dev.ps1 stop && dev.ps1 start`).

### 🐧 Opção B — Linux/macOS sem Docker

```bash
./scripts/setup.sh               # mesmo setup idempotente (Postgres embarcado em ~/.local)
./scripts/dev.sh start           # Postgres + migrations + seed + API + Web
./scripts/dev.sh status
```

Ou manualmente:

```bash
cp .env.example .env             # preencha DATABASE_URL, JWT_SECRET, chaves...
docker compose up -d db          # ou use um Postgres local

cd services/workers && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt && alembic upgrade head
python -m src.seeds.scoring_templates

cd ../api && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000     # http://localhost:8000/docs

cd ../../apps/web && npm ci && npm run dev # http://localhost:3001
```

### 🐳 Opção C — Produção com Docker

```bash
cp .env.example .env             # preencha TODAS as variáveis (JWT_SECRET obrigatório)
docker compose up -d --build
# API :8000 · Web :3000 (mude com WEB_PORT) · pgAdmin :5050 (profile dev)
```

> ⚠️ Em produção (`ENVIRONMENT=production`): SMTP é **obrigatório** (envio falha explicitamente em vez de simular); configure também `TRACKING_BASE_URL` (ativa tracking de abertura/clique), `EMAIL_WEBHOOK_SECRET` (inbound de respostas/STOP) e `SECRETS_ENCRYPTION_KEY` (criptografia das chaves BYOK).

### Primeiro acesso

1. Abra `http://localhost:3001`
2. Em **"Cadastre-se grátis"**, crie sua conta (você vira *owner* da sua organização)
3. Siga o **tour guiado** (24 etapas) ou vá direto ao wizard: **Campanhas → Nova busca**
4. Preencha as chaves de API da organização em **Configurações** (ou use o pool global do `.env`)

### 🛠️ Scripts disponíveis

| Script | Plataforma | Função |
|---|---|---|
| `setup.ps1` / `setup.sh` (+ `.cmd`) | Win / Linux | Setup completo idempotente (Postgres embarcado, venvs, `.env`, migrations, seed, `npm ci`) |
| `dev.ps1 start\|stop\|status\|restart` | Windows | Sobe/para API + Web; aplica migrations + seed a cada start |
| `dev.sh start\|stop\|status\|restart` | Linux/macOS | Mesmo fluxo no Unix |
| `backup.ps1` | Windows | Dump custom-format + rotação; `-VerifyRestore` valida o restore contra a origem |
| `backup.sh` | Linux/Docker | Idem no Unix, lendo do container `db` quando não há `DATABASE_URL`; `--verify-restore` |

---

## 🔑 Variáveis de ambiente

Definidas no `.env` da raiz (compartilhado por API e workers). Referência completa comentada em [`.env.example`](./.env.example).

| Variável | Obrigatória | Descrição |
|---|---|---|
| `DATABASE_URL` | ✅ | Conexão PostgreSQL |
| `JWT_SECRET` | ✅ | Assinatura dos tokens JWT (gere com `openssl rand -hex 32`) |
| `GROQ_API_KEY` | ✅* | LLM de scoring/outreach (*obrigatória para qualificar) |
| `GOOGLE_API_KEY` | ✅* | Google Places (*obrigatória para coletar) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | ✅ | Usados pelos workers e pelo compose |
| `NEXTAUTH_SECRET` | ✅ | Sessão do frontend — fica em `apps/web/.env.local` (o setup gera) |
| `HUNTER_API_KEY` | — | Enriquecimento de e-mail do decisor (fallback gratuito sem ela) |
| `SECRETS_ENCRYPTION_KEY` | prod | Fernet para as chaves BYOK por organização |
| `EMAIL_WEBHOOK_SECRET` | — | Ativa webhook inbound de resposta/STOP |
| `TRACKING_BASE_URL` | prod | URL pública da API — ativa pixel de abertura/redirect de clique |
| `SMTP_*` | prod | Servidor e remetente transacional/outreach |
| `GROQ_MODEL_CLASSIFY` / `GROQ_MODEL_GENERATION` | — | Modelos LLM centralizados (troca sem tocar código) |
| `DAILY_EMAIL_LIMIT` | — | Teto diário default de envio automático por org (40) |
| `APP_BASE_URL` | — | URL do frontend para links de reset/convite |

---

## 📂 Estrutura do repositório

```
agente-prospeccao/
├── apps/
│   └── web/                    # Frontend Next.js 16 (dashboard, campanhas,
│      └── src/app/(protected)/ #   oportunidades, vendas/kanban, relatórios, configurações)
├── services/
│   ├── api/                    # FastAPI: REST + WebSocket, auth JWT, scheduler de
│   │   └── src/{routes,services,auth,db}  # cadência, job-consumer do pipeline, BI, PDF
│   └── workers/                # FONTE ÚNICA dos models + migrations Alembic;
│       └── src/{services,seeds,scripts}   # coleta/enriquecimento/scoring standalone
├── scripts/                    # setup.* · dev.* · backup.* (.sh Linux · .ps1/.cmd Windows)
├── tests/                      # Pytest (unit, sem DB) + E2E de ciclo completo (banco real)
├── docs/                       # Documentação viva em PT-BR (ver seção abaixo)
├── .github/workflows/ci.yml    # CI: web lint+tsc+build · backend compileall+pytest · migrations
├── docker-compose.yml          # db · api · web · workers · pgAdmin (profile dev)
├── .env.example                # Referência completa de configuração
├── QUICKSTART.md               # Passo a passo detalhado de inicialização
└── AGENTS.md                   # Convenções para agentes de código
```

---

## 🧪 Testes e CI

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q        # da raiz — suíte completa (unit + integração leve)
```

- Os testes **não exigem banco nem chaves reais** — dependências externas são stubadas; o E2E de ciclo completo (`tests/e2e_outreach_cycle.py`) pula sozinho sem `E2E_DATABASE_URL`.
- Verificação por camada (o que o CI roda):
  - **Web**: `npm run lint` → `npx tsc --noEmit` → `npm run build`
  - **Backend**: `python -m compileall -q services/api services/workers` → `pytest`
  - **Migrations**: `alembic upgrade head` + smoke do seed

---

## 💾 Backup e operação

Backups em formato custom (`pg_dump -Fc`) com rotação automática e teste real de restore:

```powershell
# Windows (acha o pg_dump automaticamente — instalado ou embarcado)
.\scripts\backup.ps1                        # dump em .\backups
.\scripts\backup.ps1 -RetentionDays 7       # apaga dumps > 7 dias
.\scripts\backup.ps1 -VerifyRestore         # restaura em banco temporário e compara linha a linha
```

```bash
# Linux / servidor com Docker
./scripts/backup.sh                         # usa $DATABASE_URL ou o container db
./scripts/backup.sh --verify-restore
RETENTION_DAYS=7 ./scripts/backup.sh
```

Operação diária recomendada: backup antes de cada deploy, monitor de entregabilidade ativo (pausa o envio automático sozinho se o bounce passar de 5%) e revisão semanal do painel de webhooks/jobs em **Configurações**.

---

## 🛠️ Solução de problemas

<details>
<summary><strong>"não existe a coluna X" / erro de schema após git pull</strong></summary>

Migration pendente. Os scripts de dev aplicam `alembic upgrade head` a cada start; manualmente:

```bash
cd services/workers && alembic upgrade head
```
</details>

<details>
<summary><strong>Leads ficam em NOVO sem score / falhas intermitentes de qualificação</strong></summary>

Rate-limit da Groq (HTTP 429). O sistema já faz pacing global e retry com backoff (`GROQ_MIN_INTERVAL_SECONDS`, `GROQ_MAX_RETRIES`). Se muitos leads ficarem para trás, use **"Reanalisar não pontuados"** na página da campanha — só leads sem score são reprocessados (sem queimar cota à toa).
</details>

<details>
<summary><strong>Exportação de PDF falha no Windows (erro 500 / WeasyPrint)</strong></summary>

O WeasyPrint precisa do runtime GTK/Pango. A API resolve sozinha via `pdf_report_service._setup_windows_gtk()` (GTK3-Runtime Win64). Se persistir, instale o [GTK3 Runtime](https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases) e reinicie a API.
</details>

<details>
<summary><strong>Login falha com JWT_SESSION_ERROR</strong></summary>

`NEXTAUTH_SECRET` mudou ou está ausente em `apps/web/.env.local`. Ele precisa ser **estável** — regenerá-lo derruba as sessões existentes.
</details>

<details>
<summary><strong>E-mails não saem em desenvolvimento</strong></summary>

Comportamento esperado: sem SMTP configurado a API loga `[DRY-RUN EMAIL]` em vez de enviar (em produção, falha explicitamente). Configure `SMTP_HOST/USER/PASSWORD` para envio real.
</details>

<details>
<summary><strong>Porta 8000/3001 em uso</strong></summary>

```powershell
netstat -ano | findstr :8000 ; taskkill /PID <PID> /F     # Windows
lsof -i :8000 ; kill -9 <PID>                             # Linux/macOS
```
Ou mude a porta: `API_PORT`/`WEB_PORT` antes de `dev.* start` (o Web recebe a porta dinamicamente).
</details>

<details>
<summary><strong>Web retorna 500 no dev (Windows)</strong></summary>

Cache do Turbopack corrompido. `dev.ps1` já limpa `.next` a cada start; manualmente: apague `apps\web\.next` e suba de novo. Evite caminhos de repositório com espaços/acentos.
</details>

---

## 📖 Documentação

Toda a documentação detalhada vive em [`docs/`](./docs), em português. Ordem de leitura:

| Arquivo | Conteúdo |
|---|---|
| [`context.md`](./docs/context.md) | **Estado atual** do sistema + histórico de sessões (leia primeiro) |
| [`architecture.md`](./docs/architecture.md) | Arquitetura, stack, modelo de dados, endpoints |
| [`business-rules.md`](./docs/business-rules.md) | Funil, scoring, cadência, tracking, regras de fila |
| [`roadmap-vendas.md`](./docs/roadmap-vendas.md) | Mapa-norte de evolução comercial e backlog |
| [`decisions.md`](./docs/decisions.md) | ADRs — o *porquê* das decisões técnicas |
| [`coding-standards.md`](./docs/coding-standards.md) / [`agents.md`](./docs/agents.md) | Padrões de código e runbook para agentes de IA |

Na raiz: [`QUICKSTART.md`](./QUICKSTART.md) (inicialização detalhada) e [`AGENTS.md`](./AGENTS.md) (contrato para automações).

---

## 🤝 Contribuindo

1. Leia [`docs/coding-standards.md`](./docs/coding-standards.md) e [`docs/decisions.md`](./docs/decisions.md) antes de propor mudanças.
2. Rode a verificação da camada tocada (ver [Testes e CI](#-testes-e-ci)) e inclua o resultado no PR.
3. Migrations: sempre **nova** revision (`alembic revision --autogenerate`), nunca editar existentes.
4. Descreva claramente o problema resolvido ou a funcionalidade adicionada.

---

## 📄 Licença

Este projeto é distribuído sob a licença [MIT](LICENSE).

---

<div align="center">

**Prospect.ai** — encontre, qualifique e converta. Do primeiro sinal ao contrato assinado.

</div>
