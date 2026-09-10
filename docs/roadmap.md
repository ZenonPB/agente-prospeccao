# ROADMAP 100% — Agente de Prospecção AlphaMec / Paridade Funcional Apollo-like

> **Objetivo:** levar o `agente-prospeccao` a dois alvos simultâneos:
>
> 1. **100% AlphaMec:** agente forte, genérico e útil para todas as ofertas da EJ.
> 2. **100% de paridade funcional Apollo-like:** busca de empresas/pessoas, enrichment, filtros, personas, intent, saved searches, sequences, workflows, CRM sync, data health, analytics, API e automação.
>
> **Limite importante:** paridade funcional não significa recriar do zero uma rede proprietária global com centenas de milhões de contatos. O caminho viável é uma **data network federada**: fontes próprias + públicas + providers externos intercambiáveis.

## Estado atual verificado

> **Snapshot:** 2026-09-10 · branch `feat/controlled-learning-aprovacao` ·
> Alembic `3d8e0f2a3b4c` · propostas de learning controlado pendentes de
> publicação manual, matcher ponderado (`matcher-v2`), narrativa de oportunidade
> e golden patterns por oferta entregues.

As estimativas percentuais antigas foram removidas: não havia uma métrica
reprodutível que justificasse os números. Use a matriz abaixo e
`docs/00-status-mapa.md` como fonte de verdade por capacidade.

O projeto já possui arquitetura multi-tenant, OfferProfile, OfferMatcher,
pre-scoring, discovery CNAE/Places/PNCP, enrichment, scoring, Event Discovery,
cadência, outcomes e BI básico. As ondas de confiabilidade, identidade
cross-provider, pessoas/decisores e auditoria de banco avançaram, mas ainda
faltam provider especializado, buscas salvas, workflows,
integrações CRM, Data Health, re-scoring histórico de oportunidades e operação
contínua.

### Registro de entregas verificadas

| Entrega | Status | Evidência principal |
|---|---|---|
| Onda 0 — E2E, migration QA e observabilidade | ✅ Encerrada | Merges GitHub `#139`, `#143` e `#144`, `tests/e2e_outreach_cycle.py`, trace por `correlation_id`, tokens/custo Groq. |
| Identidade cross-provider de empresas | ✅ Encerrada | `company_aliases`; commits `c69fdb1`, `5604641`, `471f2a2`, `2653493`; pipeline Places/CNAE/PNCP. |
| Person canônica e estados de resolução | ✅ Entregue no escopo atual | `persons`, `needs_review/failed`, `CompanyPersonService`; commit `4d4b176`; waterfall externo ainda parcial. |
| People Discovery opt-in e próxima ação | ✅ Encerrada | `HunterPeopleProvider` + `WebsitePeopleProvider` + `HttpPeopleProvider` federado, quota por organização, role fit por título/senioridade/departamento, gates de identidade e buyer role (`BuyerPersona` com 8 personas, fallback para `buyer_types`), snapshots e API. |
| Ação recomendada e roteabilidade | ✅ Encerrada | `NextBestActionService`, API, `NextActionCard`, integração de eventos; commits `560340c`, `d2da865`, `2de3014`, `cabe188`. |
| Auditoria de schema, performance e segurança do banco | ✅ Encerrada | Reset após backup, migrations `2c4e6f8a0d3e`, `2d5e7f9b1c3f`, `2e6f8a0c2d4e`, `2f7a9b1c3d5e`; commit `d22681f`. |

### PRs GitHub identificados no histórico

| PR GitHub | Entrega | Estado |
|---|---|---|
| `#139` | Onda 0: E2E PostgreSQL, migration QA, attribution e base operacional | ✅ Encerrado |
| `#140` | Event Discovery final, provider HTTP e fluxo inicial de eventos | ✅ Encerrado |
| `#141` | Sprint de identidade de decisores e base da Person canônica | ✅ Encerrado no escopo entregue |
| `#142` | Identidade cross-provider de empresas e provenance | ✅ Encerrado |
| `#143` | Onda 0: observabilidade de providers, correlation IDs e telemetria | ✅ Encerrado |
| `#144` | Ajustes de execução/skip dos testes PostgreSQL | ✅ Encerrado |

> Os PRs acima são os merges GitHub que aparecem no histórico. As entregas
> posteriores da branch (`4d4b176` em diante) foram feitas como commits
> incrementais e ainda não devem ser apresentadas como PRs GitHub numerados.

### Pendências encerradas no mapa operacional

| Pendência | Estado | O que foi encerrado |
|---|---|---|
| P0.1–P0.5 | ✅ Encerradas | E2E PostgreSQL controlado, migration QA, warnings, documentação e observabilidade. |
| P1.1 | ✅ Encerrada | Identidade cross-provider de empresas via `company_aliases`; merge fuzzy permanece somente para revisão. |
| P1.2 | ✅ Encerrada | Provenance de candidatos rejeitados em `prescoring_discards.provenance`, com upsert e endpoint de auditoria. |
| P1.4 | ✅ Encerrada | Validação semântica de OfferProfile no build do registry (`validate_profile`/`validate_registry`, 9 sinais incorporados, zero erros no registry padrão). |
| P1.15–P1.17 e P1.19 | ✅ Encerradas | Provider de eventos opt-in, vínculo organizador → Lead, oferta `trophies` e expiração idempotente. |
| P1.18 | 🟠 Parcial | Ação recomendada, persistência da ação de evento e UI entregues; descoberta multi-provider, timing e outreach completo ainda pendentes. |
| P1.22–P1.24 | ✅ Encerradas | Atribuição de oferta/versão/oportunidade em conversões e outcomes. |
| P1.30 | ✅ Encerrada | Comparação A/B com Wilson, amostra mínima, aprovação humana e auditoria. |
| P1.29 | 🟠 Parcial | Comparações aprovadas geram propostas versionadas, auditáveis e `PROPOSED`; publicação e aplicação ao registry de perfis ainda exigem operação explícita. |
| P1.36 | ✅ Encerrada | Gates de cascata completos: `max_cost`/`cost_spent`, `min_role_fit` + senioridade/departamento, `min_identity_confidence` e `required_buyer_role` (explícito > inferido, fallback para `buyer_types`), entidade `BuyerPersona` com 8 personas, status `buyer_role_not_matched` distinto. |
| P1.7 | ✅ Encerrada | Matcher ponderado por `signals.weights` (fórmula `matcher-v2`, `score_breakdown`); três ofertas industriais com pesos diferentes para os mesmos sinais; legado igualitário preservado sem pesos. |
| P1.10 | ✅ Encerrada | Narrativa fato/hipótese/validação derivada na leitura e exposta em `GET /api/leads/{id}/oportunidades`. |
| P1.28 | ✅ Encerrada | Golden patterns por oferta + fallback por arquétipo, com wiring no matcher (`golden:<id>` só de sinais observados). |
| P1.37 | ✅ Encerrada | Verificação assíncrona sem thread/rede oculta no resolver síncrono. |
| P1.39 | ✅ Encerrada | Roteabilidade integrada à próxima ação, à ação de evento e à UI. |
| Auditoria do banco (onda 3) | ✅ Encerrada | Tabela ausente, índices, integridade de versões, proteção de secrets em produção e verificador fortalecidos. |

### Estado do banco local

O banco local foi exportado antes do reset para `backups/` (diretório
ignorado pelo Git), reconstruído com `alembic upgrade head` e validado com
`scripts/verify_migrations.py`: **37 tabelas, 20 índices, 21 FKs e 5
constraints únicas**. O reset removeu uma revisão órfã
`c9d0e1f2a3b4`/`identity_reviews` que não pertence à cadeia atual.


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

## 2.2 Migration QA — ✅ ENTREGA (ondas 0 e 3)

Automatizar:
- banco vazio → `upgrade head`;
- versão anterior → `head`;
- constraints/FKs/indexes;
- rollback somente em DB temporário.

**Estado atual:** encerrado para o schema vigente. O verificador oficial
confirma head único, 37 tabelas, 20 índices, 21 FKs e 5 constraints únicas.
As migrations da auditoria de banco também são idempotentes.

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
`correlation_id`, `campaign_id` e `usage` (JSONB com tokens do Groq) e
preenche `cost` (estimativa USD por modelo). Discovery (Places/CNAE), Event
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

## 2.5 Sincronizar docs — ✅ operacional

Atualizar sempre:
`docs/context.md`, `docs/architecture.md`, `docs/00-status-mapa.md`, `docs/pendencias-pos-consolidacao.md`, `docs/offer-profile.md`.

`context.md`, `00-status-mapa.md`, `pendencias-pos-consolidacao.md` e este
roadmap são atualizados junto de cada onda. O snapshot de estado e o backlog
operacional continuam separados do plano de longo prazo.


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

## 3.3 Provenance — ✅ operacional no discovery e no pré-scoring

Cada dado enriquecido deve saber de onde veio. O discovery e o pré-scoring
persistem estrutura equivalente com:
`field`, `value`, `source`, `confidence`, `observed_at`, `expires_at`.

`Lead.discovery_provenance` guarda a provenance consolidada do lead; o descarte
de pré-scoring guarda providers, consultas e identificadores em
`prescoring_discards.provenance`. A cobertura de todos os campos enriquecidos
e o refresh de validade continuam pendentes.

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

## 4.4 BuyerPersona — ✅ núcleo operacional

Entidade/config (`services/prospecting/buyer_persona.py`):
- title patterns;
- seniority;
- department;
- buyer type;
- priority;
- preferred channels.

Personas iniciais:
Founder, Marketing Manager, Operations Director, Engineering Manager, Maintenance Manager, Safety Manager, Event Director, Procurement.

A entidade alimenta o gate `required_buyer_role` do waterfall e o match por
cargo; `required_buyer_role_for_profile` deriva o gate de
`decision_makers.buyer_types`. Persistência dedicada em tabela própria segue
fora do escopo até haver caso de uso (config versionada em código, validada
em P1.4).

## 4.5 Canonical Person / Employment / ContactPoint — 🟠 parcial

Persistir pessoa separadamente do lead:
- `Person`;
- `Employment`;
- `PersonContactPoint`.

O model `persons` é a entidade canônica mínima ligada a Company/organização e
carrega confiança, verificação e roteabilidade. Employment e ContactPoint
separados ainda não foram necessários para o fluxo atual; manter o modelo
mínimo até haver caso de uso comprovado.

## 4.6 People Waterfall

`OfferProfile roles → domain → providers → identity merge → role fit → contacts → verification`.

**Status atual:** ✅ operacional. `PeopleProviderRegistry` implementa o waterfall
assíncrono com deduplicação, early stopping por confiança de contato e
identidade (`min_identity_confidence`), gate de buyer role
(`required_buyer_role`, explícito > inferido, fallback para
`decision_makers.buyer_types`), role fit por título/senioridade/departamento,
orçamento (`max_cost`), telemetria de tentativas e `cost_spent`. A entidade
`BuyerPersona` (8 personas iniciais) alimenta gate e match por cargo.
Três adapters reais, todos opt-in por quota da organização e ordenados por
custo: `WebsitePeopleProvider` (site oficial, JSON-LD `Person`, sem chave),
`HttpPeopleProvider` (fonte especializada federada via `PEOPLE_DISCOVERY_URL`
+ Bearer opcional, retry, `failed` ≠ `empty`) e `HunterPeopleProvider`
(Domain Search oficial, chave + quota).

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

## 5.6 Email Verification v2 — 🟠 parcial

Somar:
- sintaxe/MX;
- provider confidence;
- bounce history;
- catch-all;
- engagement history.

O seam assíncrono `ContactVerifier` e os estados de verificação já estão em
produção no fluxo; catch-all, histórico de bounce/engagement e política de
refresh ainda faltam.

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
email verificado, distingue roteabilidade (`DIRECT_CONTACT`,
`ROUTABLE_CONTACT`, `INSTITUTIONAL`, `UNKNOWN/UNREACHABLE`) e é exposto no
detalhe do lead. A ação de eventos é persistida em `event_opportunities`.
Ainda faltam timing aprendido, cadência completa, persistência de cada decisão
de sequência e integração com todas as ações do motor v2.

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
- [✅] people search por domínio via providers opt-in (Hunter + site oficial + fonte especializada federada; role fit, gates de buyer/identidade e snapshots operacionais)
- [ ] 50+ filtros realmente úteis
- [✅] buyer roles em OfferProfile/campanhas legadas (senioridade/departamento, entidade `BuyerPersona` e `required_buyer_role` com fallback para `buyer_types` operacionais)
- [ ] natural-language search
- [ ] saved searches
- [ ] alerts
- [ ] lists
- [ ] TAM/coverage

## Data
- [🟠] firmographics (Places/CNAE/Receita/PNCP)
- [✅] people/contact data federation (registry + Hunter/site/fonte especializada opt-in; filtros, gates e snapshots operacionais)
- [🟠] email verification (seam async e status persistido; cobertura v2 pendente)
- [🟠] phone confidence/roteabilidade
- [ ] technographics
- [ ] job changes
- [ ] intent
- [ ] continuous refresh
- [🟠] waterfall enrichment (pipeline adaptativo, orçamento, role fit e provenance; refresh completo pendente)
- [✅] provenance/confidence
- [ ] company hierarchy

## Engagement
- [🟠] sequences/cadência atual (Sequence Engine v2 pendente)
- [✅] email
- [🟠] call tasks recomendadas pelo Next Best Action (timing de evento incluído; execução/tarefas v2 pendente)
- [ ] LinkedIn/manual tasks
- [ ] WhatsApp/manual steps
- [✅] reply detection
- [✅] bounce handling
- [ ] auto-pause

## Automation
- [ ] workflow engine
- [ ] triggers
- [ ] conditions
- [ ] actions
- [ ] monitoring
- [✅] enrichment jobs
- [✅] assignment/notifications

## CRM/Data Ops
- [ ] Pipedrive
- [ ] HubSpot
- [ ] Salesforce
- [ ] bidirectional sync
- [ ] bulk enrichment
- [ ] scheduled enrichment
- [ ] Data Health Center

## Intelligence
- [✅] ICP/scoring contextual
- [🟠] intent (signals e estrutura; provider real de vagas pendente)
- [✅] buyer roles (`BuyerPersona` com 8 personas, gate `required_buyer_role` e match por cargo operacionais)
- [✅] decision maker (Person canônica, Hunter/site/fonte especializada opt-in, snapshots e provenance; pipeline completo de outreach segue humano assistido)
- [✅] opportunity vectors/LeadOpportunity
- [✅] next best action determinística + UI
- [✅] métricas executivas derivadas (acionabilidade e Precision@K com estado de amostra)
- [🟠] provider optimization (métricas e custo observáveis; otimização automática pendente)
- [✅] revenue attribution via LeadOpportunity/CommercialOutcome

## Platform
- [ ] public API
- [ ] API keys
- [ ] RBAC
- [✅] audit
- [✅] quotas
- [✅] observability
- [✅] retries
- [ ] failover


# 14. Milestones de progresso

## Marco atual — base operacional encerrada
- E2E PostgreSQL e migration QA; ✅
- observabilidade de providers/correlation IDs; ✅
- identidade cross-provider de empresas; ✅
- Event Discovery → organizador → Lead → oportunidade; ✅
- atribuição de outcomes/conversões e comparação A/B; ✅
- Person canônica, verificação assíncrona e roteabilidade; 🟠 parcial no fluxo
  completo de People Discovery.
- role fit por título/senioridade/departamento, filtros de waterfall, snapshots
  imutáveis de resolução e métricas executivas; ✅

## Próximo marco — People Discovery federado completo
- outreach humano assistido sobre a base federada (decisor → ação → envio
  com aprovação humana);
- BI por vertical, consultor, canal, campanha e controlled learning;
- calibração de intent/golden por outcomes reais (P1.14) e sinais semânticos
  industriais (P1.40–P1.43).

## Marcos posteriores
- saved searches, alerts e monitoramento contínuo;
- Data Health e refresh scheduler;
- Sequence Builder v2 e Workflow Engine;
- integrações CRM bidirecionais;
- otimização automática de providers, TAM e exploration controlada.

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

| Item do plano | Estado | Evidência/observação |
|---|---|---|
| PR 01 — E2E PostgreSQL + migration QA | ✅ Encerrado | Merge `#139`/`#144`; E2E real e verificador de schema. |
| PR 02 — observabilidade (trace, tokens, custo) | ✅ Encerrado | Merge `#143`; `provider_execution_metrics` e trace org-scoped. |
| PR 03 — identidade cross-provider de empresas | ✅ Encerrado | Merge `#142`; `company_aliases` integrado a Places/CNAE/PNCP. |
| PR 04 — Person canônica/estados de resolução | ✅ Entregue no escopo atual | Commit `4d4b176`; `persons`, `needs_review`, `failed`, `ContactVerifier`. |
| PR 05 — People Provider Registry + waterfall | ✅ Encerrado | Hunter/site opt-in, fonte especializada federada via endpoint próprio (`HttpPeopleProvider`, opt-in duplo), orçamento, role fit por título/senioridade/departamento, gates de identidade e buyer role, `BuyerPersona` com 8 personas, provenance e snapshots de resolução. |
| PR 09 — outcome → LeadOpportunity | ✅ Encerrado | Atribuição persistida em outcomes/conversões. |
| PR 15 — Event Provider | ✅ Encerrado | Merge `#140`; provider HTTP opt-in com retry e estados. |
| PR 16 — evento → organizador → Lead | ✅ Encerrado | Deduplicação, Company/Lead e provenance. |
| PR 17 — troféus → decisor → ação | 🟠 Parcial | Ação persistida, timing incluído e exibida; provider especializado e outreach assistido ainda pendentes. |
| PR 28 — Next Best Action | ✅ Entregue no escopo atual | `NextBestActionService`, roteabilidade, API e `NextActionCard`; motor de sequência v2 pendente. |
| PR 30 — reply/bounce automation | ✅ Entregue no escopo atual | Inbound, supressão e pausa/controle existentes; ampliar condições no motor v2. |
| PR 41 — A/B statistics | ✅ Encerrado | Wilson, amostra mínima, aprovação e auditoria. |
| PR 45 — scale/security hardening | 🟠 Parcial | Índices, migrations, backup/reset, Fernet e verificador entregues; RLS, rotação e retenção LGPD ainda pendentes. |

> Os IDs `PR 01`–`PR 45` são **itens conceituais do roadmap**, não números dos
> Pull Requests GitHub. As referências `#139`–`#144` acima são os merges reais;
> quando há commit verificável posterior, ele aparece explicitamente na coluna
> de evidência. O histórico completo permanece no log do repositório.

### Itens conceituais ainda pendentes

| Itens | Estado atual | Próxima entrega esperada |
|---|---|---|
| PR 06–08 | 🟠 Parciais | `BuyerPersona` com 8 personas e match por cargo entregues; busca avançada de pessoas/empresas e Search Builder continuam planejados. |
| PR 10 | ✅ Entregue no escopo atual | Snapshots append-only de oportunidade, vínculo de venda ao snapshot e política explícita de re-scoring (migração `3a5b7c9d1e2f`). |
| PR 11–14 | 🟠 Estruturais/parciais | Provider de vagas, sinais semânticos industriais, technographics e Intent v2. |
| PR 18 | ⬜ Planejado | EventSeries e rebuy/recorrência de eventos. |
| PR 19–20 | 🟠 Parciais | OfferProfiles dedicados para impressão 3D e corte a laser. |
| PR 21–24 | 🟠 Parciais | Freshness/refresh, Data Health e verificação telefônica. |
| PR 25–27 | ⬜ Planejados | Saved Searches, Watches e Account Monitoring. |
| PR 29 | ⬜ Planejado | Sequence Builder v2. |
| PR 31–32 | ⬜ Planejados | Workflow Engine e interface de workflows. |
| PR 33–36 | ⬜ Planejados | Adapters e sincronização bidirecional com Pipedrive, HubSpot e Salesforce. |
| PR 37–40 | 🟠 Parciais | Métricas executivas e Precision@K derivadas entregues; cortes avançados, TAM e learning controlado pendentes. |
| PR 42–44 | 🟠 Parciais | Public API v1, API keys/RBAC e camada de uso/quota para produto externo. |


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
