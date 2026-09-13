# Arquitetura — Agente de Prospecção AlphaMec

> **LIVE · atualizado em 2026-09-13.** Estado base: `main` após PR #171; PR
> #172 em validação. `docs/README.md` define a hierarquia documental.

## Visão geral

```text
Next.js Web
   ↓ JWT + X-Organization-Id
FastAPI API
   ├─ Auth / Organizations / Membership
   ├─ Campaigns / Search / CRM / Analytics
   ├─ Opportunity / Company / Person 360
   └─ Job queue + WebSocket progress
          ↓
PostgreSQL 16
          ↑
Pipeline / Workers
   ├─ Discovery federation
   ├─ Entity resolution + provenance
   ├─ Pre-scoring
   ├─ Enrichment waterfall
   ├─ Offer matching / scoring
   ├─ Decision maker resolution
   ├─ Sequences / workflows / tasks
   └─ outcomes / learning / telemetry
```

## Monorepo

- `apps/web`: Next.js, React Query, Tailwind e componentes de UI.
- `services/api`: FastAPI, auth, endpoints, job consumer, CRM/analytics.
- `services/workers`: domínio compartilhado, providers, models, migrations e
  motores de discovery/enrichment/scoring/learning.
- `tests`: unitários + persistência PostgreSQL + E2E.
- `docs`: documentação LIVE, runbooks, ADRs e snapshots históricos.

## Modelo de domínio canônico

```text
Organization
 ├─ Membership / User
 ├─ Company
 │   ├─ CompanyAlias
 │   ├─ Person
 │   └─ Lead (contexto comercial/campanha)
 │       ├─ LeadOpportunity [0..N ofertas]
 │       │   └─ LeadOpportunitySnapshot [append-only]
 │       ├─ LeadActivity
 │       ├─ CommercialTask
 │       ├─ SequenceEnrollment / Execution
 │       ├─ WorkflowRun
 │       ├─ Feedback
 │       └─ CommercialOutcome
 ├─ Campaign
 ├─ OfferProfileVersion
 └─ provider/secrets/quotas/audit
```

**Company** representa a conta canônica. **Person** representa a pessoa/decisor
canônico. **Lead** representa o contexto comercial de uma conta em uma
campanha/carteira. **LeadOpportunity** representa uma oferta específica que a
conta pode comprar. Uma empresa pode ter múltiplas oportunidades simultâneas.

## Multi-tenancy

`organization_id` é parte do contrato de segurança, não apenas um filtro de
interface. Regras:

1. recurso raiz sempre é carregado por `(id, organization_id)`;
2. relações com `organization_id` são filtradas novamente;
3. relações sem `organization_id` só são acessadas depois de provar que o pai
   pertence ao workspace;
4. acesso cross-workspace retorna 404 quando possível para não revelar
   existência;
5. CONSULTOR ainda passa pelo escopo de carteira (`consultant_lead_scope`);
6. testes reais em PostgreSQL cobrem UUID conhecido do outro workspace.

## OfferProfile e runtime por workspace

O catálogo base vive em `services/prospecting/default_profiles.py`. Publicações
controladas por organização vivem em `OfferProfileVersion`.

```text
catálogo base
   + versão ativa publicada para Organization
   ↓
build_effective_registry(db, organization_id)
   ↓
registry efetivo
   ↓ ContextVar do job
Discovery → PreScore → Enrichment → Scoring → OfferMatcher → Decision Maker
```

No PR #172, o registry efetivo é ligado ao job por `ContextVar`. Isso evita
estado global mutável e permite que jobs concorrentes de workspaces diferentes
vejam overlays diferentes. `build_effective_registry` sempre parte de
`get_base_registry()` para que o overlay A nunca contamine a construção de B.
Falha de resolução do registry faz o job falhar fechado.

## Pipeline

1. request cria `Job` PENDING;
2. `jobs_consumer` faz claim atômico com `FOR UPDATE SKIP LOCKED`;
3. materializa OfferProfile registry da organização;
4. `run_pipeline` resolve campanha/oferta e executa discovery;
5. identity resolution deduplica Company cross-provider;
6. pre-scoring evita enrichment caro em candidatos fracos;
7. waterfall de enrichment respeita estratégia/custo/gates;
8. scoring + OfferMatcher persistem oportunidade e snapshot;
9. decisor/contato e próxima ação são resolvidos;
10. providers e scoring persistem telemetria/correlation ID;
11. resultado é exposto ao CRM/BI/learning.

## Unified Data Network

Providers são adapters intercambiáveis. Estratégia por capability pode usar
federation/planner, custos, quotas, status e opt-in. Dados externos devem
carregar provenance, confidence e timestamps quando disponíveis. Provider caro
não deve executar antes de gates baratos.

## CRM

A fonte de verdade interna substitui a planilha progressivamente:

- Kanban e status/owner em `Lead`;
- tarefas em `CommercialTask`;
- histórico em `LeadActivity` + eventos reais derivados;
- oportunidades em `LeadOpportunity`;
- outcomes atribuídos à oportunidade;
- sequences/workflows persistidos;
- Opportunity 360 read-only entregue;
- Company 360/Person 360 read-only em validação no PR #172.

Não criar `Proposal`, `Contract` ou `Note` apenas para preencher UI. Essas
entidades só entram quando houver regra e ciclo de vida canônicos comprovados
no UAT.

## Controlled learning

```text
outcomes + feedback
   ↓ análise/compare
CommercialComparison
   ↓ aprovação humana
ControlledLearningProposal
   ↓ publicação explícita
OfferProfileVersion ativa por workspace
   ↓
registry efetivo do próximo job
```

Nunca há atualização silenciosa da produção. Publicação é versionada e rollback
é explícito/exato.

## Frontend

Regras de arquitetura:
- React Query para cache/estado de servidor;
- requests autenticados incluem `X-Organization-Id`;
- páginas 360 são comerciais, não dumps técnicos;
- loading/error/empty states obrigatórios;
- semântica, foco e targets mínimos de interação;
- listas pesadas paginadas/filtradas no backend;
- nada de fetch duplicado em loops/N+1 de UI.

## Observabilidade e qualidade

CI oficial executa:
- compileall Python;
- `pytest -W error`;
- migrations em PostgreSQL real + segunda execução/idempotência + schema verify;
- E2E crítico e invariantes de concorrência/tenant quando aplicáveis;
- web lint + TypeScript + production build.

Métricas de providers, custos, tokens e correlation IDs permitem investigar
campanhas. Merge só ocorre quando todos os checks do mesmo HEAD estão verdes.
