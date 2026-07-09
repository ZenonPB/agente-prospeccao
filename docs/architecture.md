# Arquitetura

## Visão Geral

Dois blocos que se comunicam via banco de dados:

- **Python workers** — agentes em background (coleta, enriquecimento, scoring, outreach)
- **Next.js** — frontend + API routes

## Stack

| Camada | Tecnologia | Status |
|---|---|---|
| Workers | Python 3.12+ | ✅ |
| HTTP (workers) | httpx (AsyncClient — tudo async) | ✅ |
| Banco | PostgreSQL | ✅ |
| ORM | SQLAlchemy + Alembic | ✅ |
| Configuração | pydantic-settings + python-dotenv | ✅ |
| IA scoring | Groq — `llama-3.1-8b-instant` | ✅ |
| IA mensagens | Groq — `llama-3.3-70b-versatile` | ⏳ Fase 3 |
| Coleta | Google Places API (New) | ✅ |
| Frontend | Next.js 16 + React 19 + TypeScript | ✅ |
| UI Components | shadcn/ui (base-nova) | ✅ |
| Auth | NextAuth.js (Google/GitHub) | ✅ Configurado |
| Gráficos | Recharts | ✅ |
| Estado global | Zustand | ✅ |
| Estado assíncrono | TanStack Query | ✅ |
| Drag-and-drop | @hello-pangea/dnd | ✅ |
| E-mail (fase 3) | Resend | ⏳ |
| Agendamento (fase 3) | Cal.com self-hosted | ⏳ |

## Estrutura de Pastas

```
agente-prospeccao/
├── apps/
│   └── web/                          ← Frontend Next.js
│       └── src/
│           ├── app/
│           │   ├── (auth)/login/     ← Login OAuth
│           │   ├── (protected)/      ← Rotas autenticadas
│           │   │   ├── dashboard/    ← Visão geral
│           │   │   ├── campanhas/    ← Buscas de leads
│           │   │   ├── oportunidades/← Leads qualificados
│           │   │   ├── pipeline/     ← Monitor tempo real
│           │   │   └── vendas/       ← Kanban negociações
│           │   └── api/auth/         ← NextAuth handler
│           ├── components/
│           │   ├── ui/               ← shadcn/ui (20+ componentes)
│           │   ├── layout/           ← Sidebar, Header
│           │   ├── dashboard/        ← Metrics, FunnelChart, etc.
│           │   ├── campanhas/        ← CampaignList
│           │   ├── oportunidades/    ← LeadList
│           │   ├── pipeline/         ← PipelineMonitor
│           │   └── vendas/           ← KanbanBoard
│           ├── lib/                  ← auth.ts, utils.ts
│           ├── stores/               ← Zustand store
│           └── types/                ← Interfaces TypeScript
├── docs/
│   ├── context.md                    ← Estado atual (ler primeiro)
│   ├── architecture.md               ← Este arquivo
│   ├── business-rules.md             ← Regras de negócio
│   ├── interface.md                  ← Requisitos UX
│   ├── decisions.md                  ← Decisões técnicas
│   ├── coding-standards.md           ← Padrões de código
│   ├── agents.md                     ← Regras para agentes IA
│   └── product-vision.md             ← Visão do produto
└── services/
    └── workers/                      ← Backend Python
        └── src/
            ├── config/settings.py
            ├── database/
            │   ├── models.py
            │   └── session.py
            ├── services/
            │   ├── places_service.py
            │   ├── technical_enrichment_service.py
            │   └── scoring_service.py
            └── main.py
```

## Pipeline Completo

```
[1. Coleta]
places_service.py
→ Lead com status=NOVO

[2. Enriquecimento Técnico]
technical_enrichment_service.py
→ tabela enrichments preenchida
→ status=ANALISADO

[3. Enriquecimento de Contatos]  ← Fase 3
contact_enrichment_service.py
(Hunter.io + WHOIS + CNPJ + Google Search)
→ tabela contacts preenchida

[4. Scoring / IA]
scoring_service.py (Groq llama-3.1-8b)
→ qualification_score, qualification_reason, primary_need
→ status=QUALIFICADO (score >= 60) ou DESQUALIFICADO

[5. Outreach]  ← Fase 3
outreach_service.py (Groq llama-3.3-70b)
→ mensagem personalizada em messages.ai_generated_draft
→ envio via Resend
→ status=CONTATADO

[6. Reunião]  ← Manual
Desenvolvedor conduz a reunião
```

## Modelo de Dados

### `leads`
Entidade central. Representa uma empresa prospectada.
- id (UUID PK)
- place_id (unique nullable)
- company_name, website, phone, email, category
- city, state, country
- status (NOVO → ANALISADO → QUALIFICADO/DESQUALIFICADO → CONTATADO → RESPONDIDO → REUNIAO_MARCADA → PERDIDO)
- qualification_score (0-100), qualification_reason, primary_need
- campaign_id (FK nullable)
- created_at, updated_at

### `campaigns`
Buscas de leads por segmento/região.
- id, user_id (FK), name
- target_service, target_segment, target_city, target_state, target_country
- status (ACTIVE/PAUSED/COMPLETED/ARCHIVED)
- created_at, updated_at

### `enrichments`
Dados técnicos do site.
- id, lead_id (FK)
- website_exists, ssl_ok, https_redirect_ok
- responsive_design, cms, lighthouse_score
- seo_errors (JSONB), load_time_ms
- security_issues (ARRAY String)
- raw_technical_data (JSONB)

### `contacts` ← Fase 3
Decisores associados a um lead.
- id, lead_id (FK)
- name, role, email, phone, linkedin
- confidence (0-100), source

### `messages` ← Fase 3
Mensagens enviadas/recebidas.
- id, lead_id (FK), channel (EMAIL/WHATSAPP/LINKEDIN)
- content, ai_generated_draft
- sent_at, responded_at, is_response

### `conversions` ← Futuro
Aprendizado contínuo da IA.
- id, lead_id (FK), converted_at
- service_sold, contract_value
- outreach_message_used, time_to_close_days

### `jobs`
Controle de processamento assíncrono.
- id, campaign_id (FK nullable)
- job_type, status, payload (JSONB)
- created_at, started_at, completed_at, error_message
