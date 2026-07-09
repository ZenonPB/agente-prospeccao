# Arquitetura

## Visão Geral

Três camadas que se comunicam via banco de dados e API:

- **Python workers** — agentes em background (coleta, enriquecimento, scoring)
- **FastAPI** — API REST + WebSocket (bridge entre frontend e workers)
- **Next.js** — frontend (interface do usuário)

```
┌─────────────┐     HTTP/WS      ┌─────────────┐     SQL      ┌─────────────┐
│   Next.js   │ ◄──────────────► │   FastAPI   │ ◄──────────► │  PostgreSQL │
│  (frontend) │                  │  (API REST) │              │   (banco)   │
└─────────────┘                  └─────────────┘              └─────────────┘
                                        │
                                        │ importa
                                        ▼
                                 ┌─────────────┐
                                 │   Workers   │
                                 │  (serviços) │
                                 └─────────────┘
```

## Stack

| Camada | Tecnologia | Status |
|---|---|---|
| Workers | Python 3.12+ | ✅ |
| HTTP (workers) | httpx (AsyncClient) | ✅ |
| API | FastAPI + uvicorn | ✅ |
| Banco | PostgreSQL | ✅ |
| ORM | SQLAlchemy + Alembic | ✅ |
| Config | pydantic-settings + python-dotenv | ✅ |
| IA scoring | Groq — `llama-3.1-8b-instant` | ✅ |
| IA mensagens | Groq — `llama-3.3-70b-versatile` | ⏳ Fase 3 |
| Coleta | Google Places API (New) | ✅ |
| Frontend | Next.js 16 + React 19 + TypeScript | ✅ |
| UI Components | shadcn/ui (base-nova) | ✅ |
| Auth | NextAuth.js (Google/GitHub) | ✅ |
| Gráficos | Recharts | ✅ |
| Estado | Zustand + TanStack Query | ✅ |
| DnD | @hello-pangea/dnd | ✅ |
| E-mail | Resend | ⏳ Fase 3 |

## Estrutura de Pastas

```
agente-prospeccao/
├── apps/
│   └── web/                          ← Frontend Next.js
│       └── src/
│           ├── app/
│           │   ├── (auth)/login/
│           │   ├── (protected)/
│           │   │   ├── dashboard/
│           │   │   ├── campanhas/
│           │   │   ├── oportunidades/
│           │   │   ├── pipeline/
│           │   │   └── vendas/
│           │   └── api/auth/
│           ├── components/
│           │   ├── ui/               ← shadcn/ui
│           │   ├── layout/           ← Sidebar, Header
│           │   ├── dashboard/
│           │   ├── campanhas/
│           │   ├── oportunidades/
│           │   ├── pipeline/
│           │   └── vendas/
│           ├── lib/, stores/, types/
├── services/
│   ├── api/                          ← FastAPI (NOVO)
│   │   ├── main.py
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── config/settings.py
│   │       ├── db/
│   │       │   ├── session.py
│   │       │   ├── dependencies.py
│   │       │   └── models.py
│   │       └── routes/
│   │           ├── leads.py
│   │           ├── campaigns.py
│   │           └── metrics.py
│   └── workers/                      ← Python workers
│       └── src/
│           ├── config/settings.py
│           ├── database/
│           │   ├── models.py
│           │   └── session.py
│           ├── services/
│           │   ├── places_service.py
│           │   ├── technical_enrichment_service.py
│           │   └── scoring_service.py
│           └── main.py
└── docs/
```

## API REST — Endpoints

### Leads
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/leads` | Lista com filtros (status, campaign_id, search, min_score) |
| GET | `/api/leads/stats` | Totais e média de score |
| GET | `/api/leads/{id}` | Detalhe do lead |

### Campanhas
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/campaigns` | Lista com lead_count e avg_score |
| GET | `/api/campaigns/{id}` | Detalhe da campanha |

### Métricas
| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/metrics` | Métricas do dashboard + funnel data |

### Próximos
| Método | Rota | Descrição |
|--------|------|-----------|
| WS | `/ws/pipeline` | Eventos em tempo real |

## Pipeline Completo

```
[1. Coleta]
places_service.py
→ Lead com status=NOVO

[2. Enriquecimento Técnico]
technical_enrichment_service.py
→ tabela enrichments preenchida

[3. Scoring / IA]
scoring_service.py (Groq llama-3.1-8b)
→ qualification_score, qualification_reason, primary_need
→ status=QUALIFICADO (score >= 60) ou DESQUALIFICADO

[4. Outreach]  ← Fase 3
outreach_service.py
→ mensagem personalizada
→ envio via Resend
→ status=CONTATADO

[5. Reunião]  ← Manual
```

## Modelo de Dados

### `leads`
- id (UUID PK), place_id, company_name, website, phone, email, category
- city, state, country
- status, qualification_score, qualification_reason, primary_need
- campaign_id (FK), created_at, updated_at

### `campaigns`
- id, user_id (FK), name
- target_service, target_segment, target_city, target_state, target_country
- status, created_at, updated_at

### `enrichments`
- id, lead_id (FK)
- website_exists, ssl_ok, https_redirect_ok, cms, load_time_ms
- security_issues, raw_technical_data

### `jobs`
- id, campaign_id (FK), job_type, status
- payload, created_at, started_at, completed_at, error_message
