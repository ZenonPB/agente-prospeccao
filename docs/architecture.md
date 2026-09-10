# Arquitetura atual

> **Fonte operacional:** este documento descreve o código presente no branch
> atual, não o plano histórico de consolidação. Snapshot: 2026-09-09 · branch
> `feat/people-discovery-completo` ·
> Alembic head `2e6f8a0c2d4e`.
>
> Para status por capacidade e backlog, consulte `docs/00-status-mapa.md` e
> `docs/pendencias-pos-consolidacao.md`. Para regras de negócio, consulte
> `docs/business-rules.md`.

## Visão geral

O Prospect.ai é uma plataforma multi-tenant de prospecção B2B. O sistema é
dividido em três camadas, com PostgreSQL como fonte compartilhada de estado:

```text
Next.js/React
     │ REST (JWT) + WebSocket autenticado
     ▼
FastAPI ───────────────► PostgreSQL ◄────────────── Workers Python
     │                         ▲                         │
     └──── jobs em background ─┘                         │
                  coleta, enrichment e scoring           │
```

- **Web (`apps/web`)**: autenticação NextAuth, campanhas, leads, oportunidades,
  vendas, relatórios e configurações.
- **API (`services/api`)**: autenticação/autorização, isolamento por
  organização, REST, WebSocket, consumidor de jobs, scheduler de cadência,
  eventos, outcomes e BI.
- **Workers (`services/workers`)**: serviços assíncronos de coleta,
  enriquecimento, scoring, matching de ofertas, discovery e contatos. Define
  os modelos SQLAlchemy e as migrations; a API apenas os reexporta.

Nenhuma análise técnica de site faz sondagem ativa: o enrichment é passivo e
usa apenas conteúdo publicamente acessível.

## Stack e configuração

| Camada | Tecnologia |
|---|---|
| Web | Next.js 16, React 19, TypeScript, TanStack Query, Zustand, shadcn/ui sobre `@base-ui/react` |
| API | FastAPI, uvicorn, SQLAlchemy, pydantic-settings, slowapi |
| Workers | Python async, `httpx.AsyncClient`, SQLAlchemy 2, Alembic |
| Banco | PostgreSQL |
| Auth | JWT compartilhado entre NextAuth e FastAPI, bcrypt |
| IA | Groq; modelos configuráveis por `GROQ_MODEL_CLASSIFY` e `GROQ_MODEL_GENERATION` |
| Provedores | Google Places, Receita/CNPJ/CNAE, Hunter opcional, provider HTTP de eventos opt-in |
| BI | Agregações FastAPI, Recharts/Leaflet no Web e PDF via WeasyPrint |

As configurações são carregadas pelos respectivos `settings.py`. A API exige
`DATABASE_URL` e `JWT_SECRET`; o worker exige `DATABASE_URL`, `GROQ_API_KEY` e
`GOOGLE_API_KEY`. Secrets por organização ficam criptografados em
`organization_secrets` e nunca são devolvidos pela API.

## Fluxos operacionais

### Pipeline de empresas

`POST /api/pipeline/start` apenas cria um `Job`. O `jobs_consumer` reivindica o
job e executa `pipeline_worker` fora da request; o progresso é publicado no
WebSocket `/api/pipeline/ws/{job_id}`.

```text
Campaign (opcional)
  → OfferProfileResolver (oferta explícita ou fallback legado)
  → DiscoveryPlanner / DiscoveryExecutor
  → Google Places, CNAE/Receita ou PNCP
  → identidade cross-provider por Company/aliases
  → Candidate pre-scoring determinístico
  → Lead
  → enrichment adaptativo passivo
  → scoring contextual Groq + evidências
  → OfferMatcher (múltiplas LeadOpportunity)
  → ContactEnrichment/Decision Maker (resolved/partial/needs_review/not_found/failed)
  → Company/Person canônicas + outreach e cadência
```

O `OfferProfile` orienta providers, orçamento, sinais e versão. Campanhas
legadas continuam funcionando por `target_service`/`target_segment`; o
resolver registra `resolved_from` para tornar o fallback observável. O
`DiscoveryExecutor` usa adapters reais de Places/CNAE e pula explicitamente um
provider sem credencial ou registro.

### Event Discovery

O pipeline aceita `source=events` em `POST /api/pipeline/start`. Esse é um fluxo
separado do scoring de leads:

```text
EventDiscoveryProvider
  → validação e normalização do evento
  → status do provider (ok/empty/failed/skipped)
  → deduplicação por URL ou provider + identificador
  → OrganizerResolver + EventTimingScorer
  → EventOpportunityService
  → event_opportunities
  → vínculo seguro com Company/Lead quando há nome oficial e confiança suficiente
```

`EVENT_DISCOVERY_URL` habilita o `HttpEventDiscoveryProvider` explicitamente;
`EVENT_DISCOVERY_TOKEN` é Bearer opcional e as retentativas são controladas por
`EVENT_DISCOVERY_MAX_RETRIES`. Sem URL, o provider externo permanece desligado.
O provider HTTP aceita uma lista JSON ou `{ "events": [...] }` e distingue erro
de rede/HTTP/JSON de lista vazia.

O job de eventos associa eventos futuros vinculados a um lead à oportunidade
`trophies` por meio do `OfferMatcher`, com upsert idempotente em
`lead_opportunities`. Ele **não** resolve automaticamente decisor nem dispara
outreach; essas etapas permanecem no loop humano e são pendência
(`docs/pendencias-pos-consolidacao.md`).

### Outcomes e comparação A/B

Conversões e resultados comerciais são atribuídos a uma oferta, versão e, quando
disponível, `lead_opportunity_id`. `commercial_outcomes` é a fonte persistida
para métricas por organização, oferta, versão e período.

`GET /api/intelligence/outcomes` lista outcomes e métricas. `GET
/api/intelligence/comparisons` calcula e persiste uma comparação de versões com
intervalos de Wilson e amostra mínima. Uma versão só pode ser aprovada por
manager/owner quando a comparação for conclusiva; a aprovação grava actor,
data, evidência e `AB_COMPARISON_APPROVED` em `org_audit_log`.

O módulo `services/prospecting/learning_metrics.py` continua contendo o
comparador e registry in-memory usados pelo serviço da API e por testes; ele não
é a fonte de persistência. A persistência operacional está em
`commercial_outcomes` e `commercial_comparisons`.

## API pública principal

Todos os endpoints abaixo usam o prefixo `/api`, salvo o WebSocket e tracking
público. A autenticação/organização é aplicada por dependências FastAPI.

| Grupo | Rotas representativas |
|---|---|
| Auth | `/auth/register`, `/auth/login`, reset/change password, `/auth/profile` |
| Org | `/orgs/me`, `/orgs/my-organizations`, membros, convites, secrets, auditoria, metas e usage |
| Campanhas | `/campaigns`, importação CSV/Sheets, brief, templates e learning de score |
| Leads | `/leads`, detalhe, enrichment, mensagens, cadência, score feedback, oportunidades, conversão e pós-venda |
| Pipeline | `POST /pipeline/start`, `GET /pipeline/jobs`, `/api/pipeline/ws/{job_id}` |
| Intelligence | `GET /intelligence/events`, `/outcomes`, `/comparisons` e aprovação A/B |
| BI | `/metrics` e `/analytics/*`, incluindo funnel, consultores, deliverability, variantes e PDF |
| Integrações | webhooks inbound/outbound, tracking, CRM paste e playbooks |

O WebSocket exige a primeira mensagem `{"type":"auth","token":"..."}` e
valida que o job pertence à organização do usuário. O token não vai na query
string.

## Modelo de dados relevante

Os modelos vivem em `services/workers/src/database/models.py`. A API importa-os
por `services/api/src/db/models.py`.

- **Tenant e acesso:** `organizations`, `users`, `organization_members`,
  `organization_secrets`, `provider_usage`, `provider_execution_metrics`,
  `org_audit_log`.
 - **Prospecção:** `campaigns`, `campaign_scoring_templates`, `jobs`, `leads`,
`companies`, `company_aliases`, `persons` (canônica com confiança/verificação/
acionabilidade), `company_records`, `enrichments`,
`prescoring_discards`, `discovery_provenance` em `leads`.
- **Oportunidades:** `lead_opportunities` (unique por lead/oferta, com
  `offer_version`, score e evidências) e `event_opportunities` (provider,
  status, provenance, organizer, timing, lead e datas).
- **Vendas/outreach:** `contacts`, `messages`, `follow_ups`, `conversions`,
  `commercial_outcomes`, `commercial_comparisons`, atividades e notificações.
- **Feedback:** `scoring_feedback` e `template_learning` calibram o scoring
  por organização; isso é distinto de métricas comerciais A/B.

O head atual é `1a2b3c4d5e6f`, que adiciona a `persons` canônica
(identidade/contato/verificação e acionabilidade) sobre a base `ff8a9b0c1d2e`
(`company_aliases` cross-provider + `correlation_id`/`campaign_id`/`usage` em
telemetria de providers). A resolução de decisores distingue
`resolved/partial/needs_review/not_found/failed`; verificação de e-mail roda
em `ContactVerifier` async com serviço injetado, sem thread no resolver.
Migrations antigas não devem ser editadas.

## Tarefas e scheduler

O `lifespan` da API inicia:

- scheduler de cadência (`CADENCE_POLL_SECONDS`, default 60s);
- requeue de `PERDIDO` (`LOST_REQUEUE_DAYS`, default 90d);
- encerramento de cadências sem resposta;
- monitor de entregabilidade, que pode pausar `auto_send_email`;
- expiração de eventos (`EVENT_EXPIRATION_POLL_SECONDS`, default 1h);
- consumidor de Jobs (`JOB_POLL_SECONDS`, default 5s).

SMTP síncrono é executado em thread; chamadas externas dos workers são async.
Os jobs registram início, fim, falha, recuperação, duração e não devem expor
credenciais nos campos livres.

## Limitações atuais

- Providers externos de eventos e vagas são opt-in; não são habilitados por
  padrão nem constituem garantia de cobertura externa.
- Event Discovery já persiste evento, organizador/lead e a oportunidade `trophies`,
  mas ainda não percorre o funil completo de decisor e outreach.
- `NextBestActionService` calcula uma recomendação determinística a partir do
  snapshot do lead e é consumido pelo detalhe `GET /api/leads/{id}`. Ele não
  envia mensagens nem altera estado; providers de pessoas continuam opt-in.
- `HunterPeopleProvider` implementa o Domain Search oficial via `httpx`, com
  retry, estados de erro e provenance. A fábrica de `ContactEnrichmentService`
  só o registra quando a organização configurou a chave e a quota
  `HUNTER_API_KEY`; a quota é consumida após resposta HTTP bem-sucedida.
- `OfferProfile` e suas versões são cadastrados em código; não há CRUD
  administrativo nem rollback de publicação.
- A resolução de decisores distingue `resolved/partial/needs_review/not_found/failed`
  e mantém snapshot JSONB compatível; `Person` canônica recebe os campos de
  `Contact` via `sync_lead_entities`, mas a descoberta externa de pessoas e a
  remoção do legado `ContactVerification` com thread ainda estão pendentes.
- BI comercial expõe oferta, versão, período e amostra, mas ainda não oferece
  todos os cortes por vertical, consultor, canal, campanha e Precision@K.
- `EventOpportunityService` calcula expiração por `event_date` ou `expires_at`,
  normalizando timestamps ISO para UTC; recorrência e estados adicionais de
  evento continuam fora do escopo atual.

## Verificação do snapshot

No snapshot desta documentação foram validados:
```text
python -m pytest tests -q -W error       → 987 passed
python -m compileall -q services/api services/workers
apps/web: npm run lint → npx tsc --noEmit → npm run build
scripts/verify_migrations.py             → head 1a2b3c4d5e6f
```