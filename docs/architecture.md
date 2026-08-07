# Arquitetura

## Visão Geral

Plataforma de **prospecção B2B** em três camadas que se comunicam via banco de
dados (ORM/API) e HTTP/WebSocket:

- **Workers (Python async)** — dono da fonte única dos modelos e migrations;
  coleta (Places/CSV/CNAE), enriquecimento passivo, scoring contextual e contatos.
- **FastAPI** — API REST + WebSocket, auth JWT, isolamento multi-tenant, BI/PDF,
  scheduler de cadência e webhooks (bridge entre frontend e workers).
- **Next.js** — frontend (dashboard, campanhas, oportunidades, kanban, relatórios).

```
┌─────────────┐     HTTP           ┌─────────────┐      SQL       ┌─────────────┐
│   Next.js   │ ◄───────────────►  │   FastAPI   │ ◄──────────── ► │  PostgreSQL │
│  (frontend) │   JWT (Rest/WS)    │  (API REST) │                 │   (banco)   │
└─────────────┘                    └─────────────┘                 └─────────────┘
                                        │
                                        │ jobs/trilha (envio de coleta/scoring)
                                        ▼
                                 ┌─────────────┐
                                 │   Workers   │  (fonte única dos modelos)
                                 │  (serviços) │
                                 └─────────────┘
```

## Stack

| Camada | Tecnologia |
|---|---|
| Workers | Python 3.12+ · httpx (async) · SQLAlchemy 2 · Alembic |
| API | FastAPI + uvicorn · slowapi (rate limit) · pydantic-settings |
| Banco | PostgreSQL |
| Auth | JWT (Credentials: email/senha, bcrypt) |
| IA | Groq — `llama-3.1-8b-instant` (scoring/router) · `llama-3.3-70b-versatile` (mensagens/templates/brief) |
| Coleta | Google Places API (New) · CSV · CNAE/Receita (BrasilAPI/Minha Receita/CNPJá) |
| Enriquecimento | Hunter.io (opcional) · Receita/CNPJ · busca passiva (LinkedIn) |
| BI/PDF | WeasyPrint (HTML→PDF) · Leaflet (mapa) · Recharts |
| Frontend | Next.js 16 · React 19 · TypeScript · shadcn/ui (`@base-ui/react`) |
| Estado frontend | TanStack Query + Zustand |

## Estrutura de Pastas

```
agente-prospeccao/
├── apps/web/                          ← Frontend Next.js
│   └── src/
│       ├── app/
│       │   ├── (auth)/                ← login, register, esqueci/resetar-senha, aceitar-convite
│       │   └── (protected)/           ← dashboard, campanhas(+nova,+[id]), oportunidades([id]),
│       │                                vendas(kanban), relatorios, configuracoes(+membros)
│       ├── components/                ← ui/(shadcn), layout/, dashboard, campanhas, oportunidades, ...
│       └── lib/ (api, utils), hooks/ (use-api), stores/, types/
├── services/
│   ├── api/                           ← FastAPI (REST + WS)
│   │   ├── main.py                    ← app, CORS, rate limit, scheduler de cadência, /health
│   │   └── src/
│   │       ├── config/settings.py     ← pydantic-settings (JWT_SECRET, DATABASE_URL, CORS, ...)
│   │       ├── auth/                  ← security (jwt+bcrypt), dependencies (roles/org)
│   │       ├── db/                    ← session, models (re-export workers), dependencies
│   │       ├── middleware/rate_limit.py
│   │       ├── routes/                ← auth, invites, leads, campaigns, metrics, pipeline,
│   │       │                            scoring_templates, orgs, analytics, webhooks
│   │       ├── services/              ← csv_import, cadence, analytics, pitch, pdf_report,
│   │       │                            org, lead_activity, invite, inbound_email, email
│   │       └── pipeline_worker.py     ← dispara coleta/scoring (org + BYOK)
│   └── workers/                       ← Python workers (fonte única de modelos/migrations)
│       └── src/
│           ├── config/settings.py
│           ├── database/{models.py, session.py}
│           ├── seeds/scoring_templates.py
│           ├── services/
│           │   ├── places_service.py
│           │   ├── technical_enrichment_service.py
│           │   ├── scoring_service.py
│           │   ├── enrichment_orchestrator.py   ← orquestração (step adaptativo)
│           │   ├── contact_enrichment_service.py
│           │   ├── cnpj_service.py / cnae_discovery_service.py
│           │   ├── outreach_service.py
│           │   ├── campaign_brief_service.py / segment_suggestion_service.py
│           │   ├── template_router.py / template_generation_service.py
│           │   ├── secret_service.py (BYOK) / provider_client.py / domain_utils.py
│           │   └── main.py
├── scripts/                           ← dev.ps1 / dev.sh / backup.sh / setup.sh
├── tests/                             ← pytest (27 testes)
└── docs/
```

Os modelos são definidos **uma única vez** em `services/workers/src/database/models.py`;
a API os re-exporta em `services/api/src/db/models.py` — não há modelos duplicados.

## API REST — Endpoints (prefixo `/api`)

### Auth
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/auth/register` | Cadastro (email/senha, bcrypt) → org pessoal + membership + JWT |
| POST | `/auth/login` | Login → JWT |
| POST | `/auth/forgot-password` · `/auth/reset-password` | Reset de senha |
| POST | `/auth/change-password` · PATCH `/auth/profile` | Conta autenticada |

### Organizações / Membros / Convites
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/orgs/my-organizations` | Orgs do usuário (switcher) |
| GET | `/orgs/me` | Org ativa + papel |
| GET | `/orgs/{id}/members` · PATCH `/orgs/{id}/members/{user_id}` | Membros e `sales_role` (owner/admin) |
| GET/POST | `/orgs/{id}/invites` · `DELETE /orgs/{id}/invites/{id}` | Convites (owner/admin) |
| POST | `/invites/accept` | Aceita convite por token |
| GET/PUT/DELETE | `/orgs/{org_id}/secrets/{key_name}` | BYOK (org admin) — só expõe `configured` |
| PATCH | `/orgs/{org_id}` | `auto_send_email`, `email_from`, `daily_email_limit`, `send_window_start/end` |

### Campanhas
| Método | Rota | Descrição |
|--------|------|-----------|
| GET/POST | `/campaigns` | Lista (lead_count/avg_score) e criação |
| GET/PATCH | `/campaigns/{id}` | Detalhe + vínculo de template |
| POST | `/campaigns/{id}/reanalyze` | Reanalisa leads (reescreve scoring legado) |
| POST | `/campaigns/{id}/import` | Import CSV (multipart; dedupe, relatório) |
| POST | `/campaigns/{id}/collect-cnae` | Coleta por CNAE em background |
| POST | `/campaigns/from-brief` · `/campaigns/suggest-segment` | Criação por linguagem natural + sugestão de segmento |

### Leads
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/leads` | Lista (filtros: status, campaign, search, min_score, assigned, next_action_before) |
| GET | `/leads/stats` · `GET /leads/{id}` | Agregados e detalhe (contatos, atividades, assigned_to) |
| PATCH | `/leads/{id}` | `whatsapp`, `notes`, `next_action_at` |
| PATCH | `/leads/{id}/status` · PATCH `/leads/{id}/assign` | Status (trilha) e atribuição |
| PATCH | `/leads/{id}/negotiation` | Funil interno de negociação (`RD/ORÇAMENTO/RP`) + resultado de contrato (`APROVADO/REPROVADO/EM_ANALISE`) — gate em RESPONDIDO→PROPOSTA_ENVIADA |
| POST | `/leads/{id}/generate-messages` | Sequência de outreach (Groq 70B) |
| POST | `/leads/{id}/conversion` | Registra conversão (serviço/valor/notas) |
| POST | `/leads/{id}/enrich-contacts` | Enriquece decisores (Receita→email/LinkedIn) |
| GET | `/leads/{id}/pitch` | Pitch one-pager + site audit |
| GET/POST | `/leads/{id}/cadence` · `/leads/{id}/cadence/start` · `/leads/{id}/cadence/send/{step}` | Cadência dia 0/3/7/14 |
| POST | `/leads/{id}/opt-out` · `DELETE /leads/{id}` | LGPD: opt-out e exclusão |

### Métricas / BI
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/metrics` | Métricas do dashboard + funnel |
| GET | `/analytics/overview` · `/analytics/consultants` · `/analytics/leads-ranking` | KPIs, funil (+ negociação RD/ORÇ/RP e resultado de contrato), desempenho por consultor, ranking |
| GET | `/analytics/geo` · `/analytics/campaigns` · `/analytics/timeline` | Geo, campanhas, evolução temporal |
| GET | `/analytics/export/pdf` | PDF executivo (WeasyPrint) |
| GET/POST/PATCH | `/scoring-templates` | CRUD de templates (globais + da org) |

### Pipeline (tempo real)
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/pipeline/start` | Inicia coleta em background → `{job_id}` |
| WS | `/ws/pipeline/{job_id}` | Stream (log, progress, lead, done, error); **auth na 1ª mensagem** (token não vai na URL) |

### Webhooks
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/webhooks/email/inbound` | Resposta → `RESPONDIDO` · STOP → `opt_out` (valida `EMAIL_WEBHOOK_SECRET`) |

All routes são filtradas pela org do usuário autenticado (dependency
`get_user_organization`); acesso cross-tenant → 404/403. Endpoints de BI e PDF
exigem `ANALYST`/`MANAGER`/owner # admin.

## Pipeline Completo

```
[1. Coleta]  Places (query, excludes, max_pages) · CSV · CNAE
             → Lead com status=NOVO (organization_id)

[2. Enriquecimento adaptativo]  enrichment_orchestrator
             · site (technical) se requires_technical_report
             · cadastral CNPJ se requires_business_data
             · leads sem site próprio são pontuados "business" (não descartados)
             → status=ANALISADO

[3. Scoring contextual]  scoring_service (Groq 8B)
             · template via router (exact→fuzzy→LLM→GENERATE_NEW→Genérico)
             → qualification_score, evidence[], priority HOT/WARM/COLD,
               pitch_angle, executive_summary
             → QUALIFICADO (score >= 60) ou DESQUALIFICADO

[4. Contatos]  contact_enrichment_service
             → email (Hunter→CNPJ→heurística) + LinkedIn (busca passiva)
             → confidence ≥ 50 p/ cadência automática

[5. Outreach]  outreach_service (Groq 70B) · cadence_service (dia 0/3/7/14)
             → humano no loop (default); envio automático só com org opt-in
             → inbound webhook: RESPONDIDO / opt_out

[6. Resultado]  atribuição/trilha → conversão → feedback no score
             → BI (analytics) + PDF executivo
```

## Modelo de Dados (fonte: `services/workers/src/database/models.py`)

- **leads** — `id`, `organization_id`, `place_id`, `company_name`, `name`, `cnpj`,
  `website`, `normalized_domain`, `phone`, `email`, `category`, `city`, `state`,
  `status`, `qualification_score/reason`, `primary_need`, `pitch_angle`,
  `suggested_subject`, `priority`, `priority_reasoning`, `executive_summary`,
  `score_factors`, `evidence`, `assigned_to_id/assigned_at`, `opt_out`,
  `whatsapp`, `notes`, `next_action_at`, `last_contacted_at`, campaign FK,
  `negotiation_stage` (RD/ORÇAMENTO/RP) + `contract_outcome`
  (APROVADO/REPROVADO/EM_ANALISE) + `outcome_date` (funil interno C.3),
  timestamps. Uniques por org: `(organization_id, place_id)`,
  `(organization_id, cnpj)`, `(organization_id, normalized_domain)`.
- **campaigns** — `organization_id`, `name`, `target_service/segment/city/state/country`,
  `places_query`, `scoring_template_id`, `analysis_profile`.
- **campaign_scoring_templates** — sinais (positive/negative/context JSONB),
  flags `requires_technical_report`/`requires_business_data`,
  `extra_instructions`, `playbook`, `is_generated`, `organization_id`.
- **organizations** — `name`, `slug`, `auto_send_email`, `email_from`,
  `daily_email_limit` e `send_window_start/end` (item 4.3: teto diário e janela
  de espalhamento do envio automático); `organization_members` ganha
  `email_from` (remetente dedicado por consultor).
- **organization_secrets** — BYOK, `encrypted_value` (Fernet).
- **contacts / company_record** — decisores, e-mails, LinkedIn, confidence; cadastro.
- **enrichments** — dados técnicos do site (SSL, CMS, load_time_ms, `raw_technical_data`).
- **jobs** — coleta/processamento (organization_id nullable).
- **lead_activities / conversions** — trilha de atribuição/status; conversões e feedback.
- **follow_ups / email_suppressions** — cadência dia 0/3/7/14; bounce/opt-out.
- **messages / analysis_profiles** — registros de envio e perfis de análise.

## Scheduler & Tarefas Assíncronas

- **Scheduler de cadência** (lifespan do FastAPI): loop asyncio
  (`CADENCE_POLL_SECONDS`, default 60s) que roda `run_due` (regra no evento loop,
  `asyncio.to_thread` para SMTP) — envia follow-ups vencidos **somente** de orgs
  com `auto_send_email`, respeitando `scheduled_at`, `opt_out` e o **throttling**
  (item 4.3: `daily_email_limit`, `send_window_start/end`, teto por hora).
  Etapas que não couberem no orçamento do dia/hora **ficam `PENDING`** (postergadas).
- **Pipeline em background**: endpoints `POST /pipeline/start`, `collect-cnae`
  criam um `Job` e disparam `pipeline_worker` com streaming via WebSocket.
- Trabalho síncrono (SMTP, import CSV) roda fora do event loop (`asyncio.to_thread`).

## Configuração & Secret

- Toda config via `settings.py` (pydantic-settings), lendo `../../.env` da raiz
  (compartilhado entre workers e API). Variáveis principais: `DATABASE_URL`,
  `JWT_SECRET`, `CORS_ORIGINS`, `GROQ_API_KEY`, `GOOGLE_API_KEY`,
  `HUNTER_API_KEY`, `SECRETS_ENCRYPTION_KEY`, `EMAIL_WEBHOOK_SECRET`,
  `TRACKING_BASE_URL` (4.2), `DAILY_EMAIL_LIMIT` (4.3),
  `CADENCE_POLL_SECONDS`, `ENVIRONMENT`.
- Chaves por org (BYOK) em `organization_secrets`, cifradas com Fernet
  (`secret_service`); serviço resolvem `BYOK → pool global`. Valores nunca expostos
  pela API (só `configured`).