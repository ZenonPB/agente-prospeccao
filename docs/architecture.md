# Arquitetura

## Visão Geral

Dois blocos que se comunicam via banco de dados:

- **Python workers** — agentes em background (coleta, enriquecimento, scoring, outreach)
- **Next.js** — frontend + API routes (fase 2)

## Stack

| Camada | Tecnologia |
|---|---|
| Workers | Python 3.12+ |
| HTTP | httpx (AsyncClient — tudo async) |
| Banco | PostgreSQL |
| ORM | SQLAlchemy + Alembic |
| Configuração | pydantic-settings + python-dotenv |
| IA scoring | Groq — `llama-3.1-8b-instant` |
| IA mensagens | Groq — `llama-3.3-70b-versatile` |
| IA avançada (futuro) | Ollama Cloud — Qwen3 / DeepSeek |
| Coleta | Google Places API (New) |
| Frontend (fase 2) | Next.js + NextAuth.js |
| E-mail (fase 3) | Resend |
| Agendamento (fase 3) | Cal.com self-hosted |

## Estrutura de Pastas
agente-prospeccao/
├── docs/
│   ├── context.md
│   ├── architecture.md
│   ├── business-rules.md
│   ├── roadmap.md
│   ├── decisions.md
│   ├── coding-standards.md
│   ├── agents.md
│   └── decisions/
│       ├── 0001-python-workers.md
│       ├── 0002-postgresql.md
│       ├── 0003-google-places.md
│       └── 0004-httpx-async.md
└── services/
└── workers/
├── venv/
└── src/
├── config/
│   └── settings.py
├── database/
│   ├── models.py
│   └── session.py
├── services/
│   ├── places_service.py
│   ├── technical_enrichment_service.py
│   ├── scoring_service.py         ← a criar
│   ├── contact_enrichment_service.py  ← a criar (fase 2)
│   └── outreach_service.py        ← a criar (fase 3)
└── main.py

## Pipeline Completo
[1. Coleta]
places_service.py
→ Lead com status=NOVO

[2. Enriquecimento Técnico]
technical_enrichment_service.py
→ tabela enrichments preenchida
→ status=ANALISADO

[3. Enriquecimento de Contatos]  ← fase 2
contact_enrichment_service.py
(Hunter.io + WHOIS + CNPJ + Google Search)
→ tabela contacts preenchida

[4. Scoring / IA]
scoring_service.py (Groq llama-3.1-8b)
→ qualification_score, qualification_reason, primary_need
→ status=QUALIFICADO (score >= 60) ou DESQUALIFICADO

[5. Outreach]  ← fase 3
outreach_service.py (Groq llama-3.3-70b)
→ mensagem personalizada em messages.ai_generated_draft
→ envio via Resend
→ status=CONTATADO

[6. Reunião]  ← manual
Desenvolvedor conduz a reunião

## Modelo de Dados

### `users`
id (UUID PK),
email, 
password_hash, 
name, 
role,
created_at, 
updated_at

### `campaigns`
id, 
user_id (FK), 
name, 
target_service, 
target_segment,
target_city, 
target_state, 
target_country,
status (ACTIVE/PAUSED/COMPLETED/ARCHIVED),
created_at, 
updated_at

### `leads`
Entidade central. Representa uma empresa prospectada.
id (UUID PK), 
place_id (unique nullable), 
company_name,
website, 
phone, 
email, 
category, 
city, 
state, 
country,
status (ver business-rules.md),
qualification_score (0-100), 
qualification_reason (Text),
primary_need (String), 
segment_opportunity (String),
campaign_id (FK nullable), 
created_at, 
updated_at

### `contacts`  ← a criar na migration
Decisores e contatos associados a um lead.
Separado de Lead para suportar múltiplos contatos por empresa.
id (UUID PK), 
lead_id (FK),
name, 
role, 
email, 
phone, 
linkedin,
confidence (Integer 0-100),
source (String — "hunter", "whois", "cnpj", "manual"),
created_at, 
updated_at

### `enrichments`
Dados técnicos do site.
id, 
lead_id (FK), 
website_exists, 
ssl_ok, 
https_redirect_ok,
responsive_design, 
cms, 
lighthouse_score,
seo_errors (JSONB), 
load_time_ms, 
security_issues (ARRAY String),
raw_technical_data (JSONB),
created_at, 
updated_at

### `messages`
id,
lead_id (FK), 
channel (EMAIL/WHATSAPP/LINKEDIN),
content, 
ai_generated_draft,
sent_at, 
responded_at, 
is_response

### `conversions`
Fonte de aprendizado contínuo da IA.
id,
lead_id (FK), 
converted_at, 
service_sold,
contract_value, 
outreach_message_used,
time_to_close_days, 
notes

### `jobs`
id,
campaign_id (FK nullable),
job_type (LEAD_COLLECTION/LEAD_ENRICHMENT/LEAD_SCORING/OUTREACH_EMAIL),
status (PENDING/IN_PROGRESS/COMPLETED/FAILED/CANCELLED),
payload (JSONB), 
created_at, 
started_at, 
completed_at, 
error_message