# ROADMAP 100% — Agente de Prospecção AlphaMec / Paridade Funcional Apollo-like

> **Objetivo:** levar o `agente-prospeccao` a dois alvos simultâneos:
>
> 1. **100% AlphaMec:** agente forte, genérico e útil para todas as ofertas da EJ.
> 2. **100% de paridade funcional Apollo-like:** busca de empresas/pessoas, enrichment, filtros, personas, intent, saved searches, sequences, workflows, CRM sync, data health, analytics, API e automação.
>
> **Limite importante:** paridade funcional não significa recriar do zero uma rede proprietária global com centenas de milhões de contatos. O caminho viável é uma **data network federada**: fontes próprias + públicas + providers externos intercambiáveis.

## Estado atual estimado

- **Meta AlphaMec:** ~74%.
- **Paridade funcional Apollo-like:** ~45%.

O projeto já possui boa arquitetura, OfferProfile, OfferMatcher, pre-scoring, discovery, CNAE/Places/PNCP, enrichment, scoring, eventos, cadência, outcomes e BI básico. **Onda 0 de confiabilidade entregue** (E2E PostgreSQL, migration QA, provider observability com correlation IDs, telemetria de tokens/custo Groq e endpoint de trace). O maior gap agora é **dados, cobertura, timing, contatos e execução contínua**.


# 1. Arquitetura-alvo

```text
Campaign / Saved Search / Trigger
        ↓
OfferProfile + BuyerPersona
        ↓
Discovery Planner
        ↓
Company / People / Event / Job Providers
        ↓
Entity Resolution + Provenance
        ↓
Pre-Scoring
        ↓
Waterfall Enrichment
        ↓
Signals + Intent + Technographics
        ↓
OfferMatcher
        ↓
LeadOpportunity (versionada)
        ↓
Decision Maker Resolution
        ↓
Verified Contact + Actionability
        ↓
Next Best Action
        ↓
Sequence / Workflow
        ↓
CommercialOutcome
        ↓
Learning + Provider Optimization
```

## Princípios obrigatórios

- Engine genérico; inteligência específica fica em `OfferProfile`.
- `UNKNOWN` nunca é tratado como `FALSE`.
- `FACT`, `INFERENCE`, `HYPOTHESIS` e `UNKNOWN` continuam separados.
- Provider caro só roda depois de filtros baratos.
- Toda informação externa tem `source`, `confidence`, `observed_at` e `expires_at`.
- Toda venda precisa ser atribuída à `LeadOpportunity` correta.
- Uma empresa pode ter múltiplas oportunidades simultâneas.
- Nenhuma capability vira `COMPLETE` por existir apenas como helper/registry/placeholder.


# 2. Fase 0 — Confiabilidade operacional

## 2.1 E2E PostgreSQL real — ✅ ENTREGA (onda 0)

Provar de ponta a ponta:

```text
Campanha → Job → Discovery → PreScore → Lead → Enrichment → Scoring
→ LeadOpportunity → Decision Maker → Outreach → Conversão
→ CommercialOutcome → BI
```

### Arquivos
`tests/e2e_outreach_cycle.py`, `services/api/src/pipeline_worker.py`, `services/api/src/jobs_consumer.py`, migrations e CI.

### DoD
- PostgreSQL real;
- migrations aplicadas;
- execução repetível;
- erros possuem estágio identificável;
- CI/job manual reproduzível.

## 2.2 Migration QA — ✅ ENTREGA (onda 0)

Automatizar:
- banco vazio → `upgrade head`;
- versão anterior → `head`;
- constraints/FKs/indexes;
- rollback somente em DB temporário.

## 2.3 Provider observability — ✅ ENTREGA (onda 0)

Padronizar:

```json
{
  "provider": "cnae",
  "status": "success|empty|failed|disabled|quota_exceeded|timeout",
  "result_count": 12,
  "duration_ms": 840,
  "cost_units": 1,
  "error_code": null
}
```

Persistir métricas por provider/job/campaign/org.

**Status:** operacional. `provider_execution_metrics` agora persiste
`correlation_id`, `campaign_id` e `usage` (JSONB gratuito com tokens do Groq) e
prenche `cost` (estimativa USD por modelo). Discovery (Places/CNAE), Event
Discovery e scoring Groq registram métricas por execução. Novo endpoint
`GET /analytics/provider-trace/{correlation_id}` devolve o trace completo de um
job (todas as medições do mesmo `correlation_id`, org-scoped — responde "por
que esta campanha trouxe poucos leads").

## 2.4 Correlation IDs — ✅ ENTREGA (onda 0)

Todo fluxo deve carregar:
`organization_id`, `campaign_id`, `job_id`, `lead_id`, `offer_key`, `correlation_id`.

**Status:** operacional. Cada execução de `run_pipeline` gera um `correlation_id`
(UUID) que é logado, propagado para todas as `ProviderExecutionMetric` do job
(discovery, eventos e scoring) e devolvido no payload final do WebSocket/job
(`correlation_id` + `provider_metrics` agregadas). O rastro permite auditar
status/latência/erro/custo de cada provider de uma execução.

## 2.5 Sincronizar docs

Atualizar sempre:
`docs/context.md`, `docs/architecture.md`, `docs/00-status-mapa.md`, `docs/pendencias-pos-consolidacao.md`, `docs/offer-profile.md`.


# 3. Fase 1 — Unified Data Network

## 3.1 DiscoveryProvider Registry

Contrato único assíncrono para:
- Google Places;
- CNAE/Receita;
- PNCP;
- CSV;
- Web Search;
- Event Search;
- Job Search;
- Company Database.

## 3.2 Company Identity Resolution cross-provider

Prioridade de match:

```text
CNPJ exato
→ domínio normalizado
→ place_id
→ nome + cidade + UF
→ fuzzy apenas para revisão
```

Persistir aliases e IDs por fonte.

**Status:** ✅ entregue. `company_aliases` registra place_id/domínio/maps_uri por
Company; a resolução (CNPJ → domínio → aliases) é usada pelo pipeline nas rotas
Places, CNAE e PNCP para mesclar provenance em vez de duplicar lead. O match
fuzzy (nome + cidade + UF) permanece apenas candidato para revisão.

## 3.3 Provenance

Cada dado enriquecido deve saber de onde veio. Criar `DataPoint` ou estrutura equivalente com:
`field`, `value`, `source`, `confidence`, `observed_at`, `expires_at`.

## 3.4 Provider Federation

Cada capability pode ter waterfall:

```text
People Search:
Provider A → Provider B → QSA → site → web
```

## 3.5 Cost model

Provider declara:
`cost_per_request`, `quota`, `rate_limit`, `expected_coverage`, `expected_precision`.

Planner usa valor esperado/custo.


# 4. Fase 2 — Company Search e People Search

## 4.1 Advanced Company Search

Criar `POST /api/search/companies` com filtros:
- localização;
- CNAE/indústria;
- porte;
- funcionários;
- receita;
- idade;
- tecnologias;
- signals;
- intent;
- keywords;
- exclusions.

Suportar `AND`, `OR`, `NOT`.

## 4.2 Natural Language Search

LLM apenas traduz linguagem natural para `SearchIntent` validado. Não chama provider diretamente.

## 4.3 People Search

Criar `POST /api/search/people` com:
- empresa/domínio;
- cargo;
- função;
- senioridade;
- buyer role;
- localização;
- status do email/telefone;
- LinkedIn.

## 4.4 BuyerPersona

Criar entidade/config:
- title patterns;
- seniority;
- department;
- buyer type;
- priority;
- preferred channels.

Personas iniciais:
Founder, Marketing Manager, Operations Director, Engineering Manager, Maintenance Manager, Safety Manager, Event Director, Procurement.

## 4.5 Canonical Person / Employment / ContactPoint

Persistir pessoa separadamente do lead:
- `Person`;
- `Employment`;
- `PersonContactPoint`.

Evitar CRM gigante; manter modelo mínimo necessário.

## 4.6 People Waterfall

`OfferProfile roles → domain → providers → identity merge → role fit → contacts → verification`.

**Status atual:** 🟠 parcial. `HunterPeopleProvider` implementa o primeiro
adapter real via Domain Search oficial, com retry, quota e estados observáveis;
ele só é ativado por chave e quota explícitas da organização. Ainda faltam
providers complementares e role fit completo por OfferProfile.

## 4.7 ActionableContactScore

Dimensões:
`identity_confidence`, `role_fit`, `email_confidence`, `phone_confidence`, `freshness`, `routability`.


# 5. Fase 3 — Enrichment, Freshness e Data Health

## 5.1 Waterfall Enrichment

Capabilities:
company, person, email, phone, technographics, social, intent.

## 5.2 TTL

Exemplo:
- company registry: 60d;
- website: 30d;
- technographics: 30d;
- employment: 30d;
- email: 30d;
- phone: 60d;
- jobs: 14d;
- events: até o evento.

## 5.3 Refresh Scheduler

Criar `RefreshStaleDataJob`.

Priorizar:
- oportunidades abertas;
- leads em sequência;
- contas de alto valor.

## 5.4 Data Health Center

Página `/data-health`:
- contatos stale;
- emails inválidos;
- missing phones;
- missing decision makers;
- job changes;
- duplicates;
- unresolved identities;
- provider failures.

## 5.5 PhoneVerificationService

Estados:
`VERIFIED`, `LIKELY_VALID`, `UNKNOWN`, `INVALID`.

## 5.6 Email Verification v2

Somar:
- sintaxe/MX;
- provider confidence;
- bounce history;
- catch-all;
- engagement history.

## 5.7 Job change

Novo emprego invalida Employment anterior e reabre enrichment/decision maker quando necessário.


# 6. Fase 4 — Intent e Technographics

## 6.1 Intent Providers reais

Implementar progressivamente:
1. `JobPostingIntentProvider`;
2. `CompanyNewsIntentProvider`;
3. `ProcurementIntentProvider`;
4. `SocialIntentProvider`;
5. `EventIntentProvider`.

## 6.2 Signals de vagas

Engenharia:
`HIRING_MECHANICAL_ENGINEER`, `HIRING_PROJECT_DESIGNER`, `HIRING_MAINTENANCE`, `HIRING_AUTOMATION`, `HIRING_CNC_OPERATOR`.

Tecnologia:
`HIRING_IT`, `HIRING_OPERATIONS`, `HIRING_DATA`.

## 6.3 News signals

`NEW_BRANCH`, `EXPANSION`, `NEW_FACTORY`, `NEW_PRODUCT`, `FUNDING`, `MANAGEMENT_CHANGE`.

## 6.4 PNCP/procurement

`TENDER_OPEN`, `SOFTWARE_PROCUREMENT`, `INDUSTRIAL_PROCUREMENT`, `EVENT_PROCUREMENT`.

## 6.5 TechnologyStackProvider

Detectar, quando possível:
WordPress, Shopify, WooCommerce, RD Station, HubSpot, Salesforce, TOTVS, Omie, Bling, Analytics, Meta Pixel, Cloudflare e stack web.

## 6.6 Intent Score v2

```text
contribution =
signal_weight × confidence × source_reliability × recency_decay
```

Combinar com saturação, não média simples.

## 6.7 Opportunity Vector

Persistir:
`icp_fit`, `need`, `intent`, `buying_power`, `reachability`, `timing`, `commercial_fit`, `overall`.


# 7. Fase 5 — Excelência por oferta AlphaMec

## Landing Page

Signals:
`NO_OWN_WEBSITE`, `HAS_INSTAGRAM`, reputação Google, Ads, CTA ruim, ausência de formulário, fluxo de conversão fraco.

Personas:
Founder, Marketing, Commercial.

## Sistemas Web / ERP

Signals:
complexidade operacional, múltiplas unidades, processos manuais, ferramentas existentes, limitações SaaS, hiring Ops/IT, crescimento.

Technographics importantes:
Bling, Omie, TOTVS, HubSpot, Sheets, portais WordPress.

Personas:
Founder, COO, Operations, Finance, IT.

## Projeto Mecânico

Signals:
`HAS_CNC`, `HAS_PRODUCTION_LINE`, `CUSTOM_MACHINERY`, `AUTOMATION`, `NEW_EQUIPMENT`, `EXPANDING_FACTORY`, `HIRING_MECHANICAL_ENGINEER`.

## Desenho Técnico

Signals:
`USINAGEM`, `CUSTOM_PARTS`, `REPLACEMENT_PARTS`, `REVERSE_ENGINEERING`, `CUSTOM_MANUFACTURING`, CAD.

## Manual de Máquinas / NR-12

Signals:
`MACHINE_MANUFACTURER`, `NR12`, `INDUSTRIAL_SAFETY`, `TECHNICAL_DOCUMENTATION`, `NEW_MACHINE`.

## Impressão 3D

Criar `OfferProfile 3d_printing`.

ICP:
R&D, hardware startups, produto, laboratórios, manufatura.

Intent:
`NEW_PRODUCT`, `PROTOTYPE`, `R&D`.

## Corte a Laser

Criar:
- `laser_cutting_technical`;
- `laser_custom_products`.

## Troféus

Manter `trophies` como oferta própria, não subproduto de laser.

### Event Discovery
Providers por família:
- MEJ;
- esportes;
- acadêmico;
- hackathons;
- corporate awards.

### EventSeries
Persistir:
`series_key`, `recurrence_confidence`, `previous_event`, `expected_next_window`.

### Rebuy Engine
Quando evento recorrente entra na janela:
`create opportunity → refresh organizer → refresh decision maker → task`.

## CaseStudyMatcher

Criar `CaseStudy` com:
`offer_key`, `segments`, `problem`, `solution`, `proof`, `assets`.

Oportunidade recebe o case mais adequado.


# 8. Fase 6 — Saved Searches, Alerts e Agente Contínuo

## 8.1 SavedProspectingSearch

Campos:
`filters`, `offer_key`, `schedule`, `owner`, `notification_policy`.

## 8.2 Alerts

Novo match:
`discover → prescore → notify/create candidate`.

## 8.3 Prospecting Watch

Exemplo:
“metalúrgicas SP 10–200 funcionários + hiring engineer”.

## 8.4 Event Watch

Exemplo:
“eventos MEJ em 30–120 dias”.

## 8.5 Account Monitoring

Monitorar:
jobs, site, news, events, contacts e decision makers.

## 8.6 Agent State Machine

Estados:
`DISCOVERED`, `NEEDS_ENRICHMENT`, `READY_TO_SCORE`, `READY_FOR_CONTACT`, `AWAITING_ACTION`, `IN_SEQUENCE`, `WAITING`, `REENGAGE`, `CLOSED`.


# 9. Fase 7 — Engagement e Next Best Action

## 9.1 Sequence Engine v2

Steps:
- email;
- phone task;
- LinkedIn task;
- WhatsApp/manual;
- research task;
- wait;
- condition.

## 9.2 Sequence Builder

Página `/sequences`.

## 9.3 Persona sequences

Templates diferentes para:
Engineering Manager, Founder, Ops Director, Event Director etc.

## 9.4 NextBestActionEngine

Entrada:
OfferProfile + Opportunity + Intent + DecisionMaker + Contactability + Cadence + EventTiming + LastInteraction.

Ações:
`SEND_EMAIL`, `CALL`, `SEND_LINKEDIN`, `WAIT`, `RESEARCH`, `RE_ENRICH`, `SEND_CASE_STUDY`, `STOP`.

Cada decisão retorna `why`, `confidence`, `evidence`, `deadline`.

**Status atual:** 🟠 parcial. `NextBestActionService` já calcula uma
recomendação determinística, respeita opt-out/identidade ambígua e o gate de
email verificado, e é exposto no detalhe do lead. Ainda faltam timing de evento,
cadência completa, persistência da decisão e integração com todas as ações da
sequência.

## 9.5 Reply/bounce automation

- bounce → invalida contato;
- reply → pausa sequence;
- meeting → encerra outreach;
- unsubscribe → blocklist.

## 9.6 Auto-pause

Pausar sequência por bounce elevado ou saúde de domínio/provedor.


# 10. Fase 8 — Workflows e CRM

## 10.1 Workflow Engine

```text
TRIGGER → CONDITIONS → ACTIONS
```

Triggers:
lead created/scored, intent detected, event detected, contact found, email verified, reply, meeting, won, data stale, saved-search match.

Conditions:
offer, score, intent, size, persona, contactability, location, provider, channel.

Actions:
add list, enroll sequence, create task, assign owner, notify, enrich, rerank, webhook, CRM sync.

## 10.2 CRM Adapters

Prioridade:
1. Pipedrive;
2. HubSpot;
3. Salesforce.

Contrato:
`CRMAdapter`.

## 10.3 Bidirectional sync

Mapear:
Company, Person, LeadOpportunity, CommercialOutcome, Owner, Activity.

## 10.4 CRM enrichment

Modos:
manual, realtime, scheduled.

## 10.5 Integration Framework

Webhooks assinados + adapters versionados.


# 11. Fase 9 — Learning e Analytics

## 11.1 Attribution correta

`CommercialOutcome → lead_opportunity_id → offer_key → offer_version`.

Não usar fallback silencioso de “maior score” para novas vendas.

## 11.2 Signal effectiveness

Calcular:
`P(reply|signal)`, `P(meeting|signal)`, `P(won|signal)`, `revenue_per_signal`.

## 11.3 Provider effectiveness

Por provider:
candidates, qualified, actionable, meetings, wins, cost, revenue, ROI.

## 11.4 Precision@K

P@10 reply, P@10 meeting, P@25 won.

## 11.5 Niche Prior

Escopo:
`organization × offer × segment`.

## 11.6 Learning controlado

1. observar;
2. recomendar alteração;
3. aprovação humana;
4. nova versão de OfferProfile;
5. rollback.

## 11.7 A/B testing

Mensagem, subject, channel, cadence, angle, CTA.

## 11.8 Exploration

Opcional:
95% exploitation / 5% exploration para reduzir selection bias.

## 11.9 TAM/Coverage

Dashboard:
market universe, ICP matches, enriched, contactable, prospected, won, penetration.


# 12. Fase 10 — Productização e escala

## Public API

Criar `/api/v1` para:
search, enrich, companies, people, opportunities, sequences, workflows, analytics.

## API keys / RBAC

Papéis:
admin, manager, seller, viewer, automation.

## Quotas e usage

Medir:
requests, provider credits, LLM tokens, emails, enriched contacts.

## Audit logs

Registrar:
who, what, when, before, after, source.

## Retry / queue / DLQ

Toda integração externa deve ter:
idempotency, retry, dead-letter e backoff.

## Multi-provider failover

Provider A falha → B quando permitido.

## Search scale

Começar com PostgreSQL/FTS. Migrar para OpenSearch/Elastic somente se métricas exigirem.

## Security hardening

JWT iss/aud, HSTS, CORS, secret rotation, webhook signatures, login lockout, PII logging policy, retention/LGPD.


# 13. Checklist de paridade funcional Apollo-like

## Prospecting
- [ ] advanced company search
- [ ] advanced people search
- [ ] 50+ filtros realmente úteis
- [ ] personas
- [ ] natural-language search
- [ ] saved searches
- [ ] alerts
- [ ] lists
- [ ] TAM/coverage

## Data
- [ ] firmographics
- [ ] people/contact data federation
- [ ] email verification
- [ ] phone confidence
- [ ] technographics
- [ ] job changes
- [ ] intent
- [ ] continuous refresh
- [ ] waterfall enrichment
- [ ] provenance/confidence
- [ ] company hierarchy

## Engagement
- [ ] sequences
- [ ] email
- [ ] call tasks
- [ ] LinkedIn/manual tasks
- [ ] WhatsApp/manual steps
- [ ] reply detection
- [ ] bounce handling
- [ ] auto-pause

## Automation
- [ ] workflow engine
- [ ] triggers
- [ ] conditions
- [ ] actions
- [ ] monitoring
- [ ] enrichment jobs
- [ ] assignment/notifications

## CRM/Data Ops
- [ ] Pipedrive
- [ ] HubSpot
- [ ] Salesforce
- [ ] bidirectional sync
- [ ] bulk enrichment
- [ ] scheduled enrichment
- [ ] Data Health Center

## Intelligence
- [ ] ICP
- [ ] intent
- [ ] buyer roles
- [ ] decision maker
- [ ] opportunity vectors
- [ ] next best action
- [ ] provider optimization
- [ ] revenue attribution

## Platform
- [ ] public API
- [ ] API keys
- [ ] RBAC
- [ ] audit
- [ ] quotas
- [ ] observability
- [ ] retries
- [ ] failover


# 14. Milestones de progresso

## 80%
- E2E PostgreSQL; ✅
- People Search real;
- Decision Maker real;
- observabilidade; ✅
- outcome attribution;
- Job Intent.

## 85%
- technographics;
- industrial semantic enrichment;
- event provider MEJ;
- event → lead → trophies;
- contact waterfall.

## 90%
- saved searches;
- alerts;
- freshness;
- Data Health;
- Next Best Action;
- personas.

## 95%
- workflows;
- CRM sync;
- advanced enrichment;
- provider optimization;
- A/B;
- TAM.

## 100% AlphaMec
- todas as ofertas com OfferProfiles;
- discovery/intent/decisor específicos;
- trophies recurrence;
- engineering semantic intelligence;
- continuous monitoring;
- commercial learning.

## 100% Apollo-like funcional
- search;
- data federation;
- enrichment;
- filters;
- personas;
- intent;
- saved searches;
- alerts;
- sequences;
- workflows;
- CRM sync;
- Data Health;
- refresh;
- API;
- analytics;
- TAM;
- automation.


# 15. Ordem recomendada de PRs

```text
PR 01 — E2E PostgreSQL + migration QA                            ✅ entregue
PR 02 — provider observability (trace, tokens, custo)            ✅ entregue
PR 03 — cross-provider company identity                          ✅ entregue
PR 04 — canonical Person/Employment/ContactPoint
PR 05 — People Provider Registry + waterfall
PR 06 — advanced People Search
PR 07 — advanced Company Search
PR 08 — BuyerPersona + Search Builder
PR 09 — outcome → LeadOpportunity attribution
PR 10 — opportunity snapshots/versioning
PR 11 — Job Intent source real
PR 12 — industrial semantic signals
PR 13 — TechnologyStackProvider
PR 14 — Intent v2
PR 15 — MEJ Event Provider
PR 16 — event → organizer → lead
PR 17 — trophies → decision maker → action
PR 18 — EventSeries + rebuy
PR 19 — 3D printing OfferProfile
PR 20 — laser OfferProfiles
PR 21 — freshness policies
PR 22 — refresh scheduler
PR 23 — Data Health Center
PR 24 — phone verification
PR 25 — Saved Searches
PR 26 — Prospecting Watches
PR 27 — Account Monitoring
PR 28 — Next Best Action
PR 29 — Sequence Builder v2
PR 30 — reply/bounce automation
PR 31 — Workflow Engine
PR 32 — Workflow UI
PR 33 — Pipedrive
PR 34 — HubSpot
PR 35 — Salesforce
PR 36 — CRM enrichment
PR 37 — provider analytics
PR 38 — signal analytics
PR 39 — TAM dashboard
PR 40 — controlled learning
PR 41 — A/B statistics
PR 42 — Public API v1
PR 43 — API keys/RBAC/audit
PR 44 — usage/quota layer
PR 45 — scale/security hardening
```


# 16. Definition of Done

Uma capability só é `COMPLETE` quando:

- [ ] possui contrato;
- [ ] implementação real;
- [ ] consumidor real;
- [ ] integração pipeline/UI;
- [ ] tenant scope;
- [ ] provenance;
- [ ] failed/empty/unknown distintos;
- [ ] retry para IO;
- [ ] observabilidade;
- [ ] persistência quando necessária;
- [ ] unit tests;
- [ ] integration tests;
- [ ] E2E quando crítica;
- [ ] documentação atualizada;
- [ ] sem placeholder tratado como sucesso;
- [ ] sem contaminação de learning;
- [ ] auditável;
- [ ] qualidade mensurável.


# 17. KPIs para declarar o sistema “bom de verdade”

## Coverage
- `company_match_rate`
- `person_match_rate`
- `actionable_contact_rate`
- `verified_email_rate`
- `verified_phone_rate`

## Quality
- `duplicate_rate`
- `stale_rate`
- `bounce_rate`
- `wrong_person_rate`

## Commercial
- `reply_rate`
- `positive_reply_rate`
- `meeting_rate`
- `proposal_rate`
- `win_rate`
- `revenue`

## Intelligence
- `Precision@10`
- `Precision@25`
- `signal_lift`
- `intent_lift`

## Cost
- `cost_per_candidate`
- `cost_per_qualified`
- `cost_per_actionable`
- `cost_per_meeting`
- `cost_per_won`


# 18. Diferencial final

A meta não é construir “um Apollo menor”.

A vantagem competitiva deve ser:

```text
Apollo-like platform capabilities
+
Brasil/local data
+
CNPJ/CNAE
+
Google Maps
+
PNCP
+
MEJ events
+
industrial semantic signals
+
offer-specific reasoning
+
event recurrence
+
case-study matching
+
AlphaMec commercial learning
```

O resultado final esperado:

> **“Qual organização realmente precisa de qual serviço, por que agora, quem decide, qual contato é confiável, qual ação deve ser tomada e qual estratégia está gerando receita?”**

Quando a plataforma conseguir responder isso continuamente, com dados frescos, métricas, workflows e cobertura multi-provider, ela terá atingido os dois objetivos: **100% AlphaMec** e **paridade funcional Apollo-like**.
