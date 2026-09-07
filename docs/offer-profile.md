# OfferProfile e oportunidades comerciais

> **Status atual:** contrato, registry, resolver e matcher estão operacionais no
> pipeline. Snapshot: 2026-09-07 · branch `feat/onda-2-event-discovery-final`.
> Este documento substitui os status históricos das fases C–H; o plano original
> está preservado em `docs/consolidacao.md`.

## Papel na arquitetura

`OfferProfile` é a configuração declarativa de uma oferta comercial. Ele
separa o arquétipo genérico da vertical e da oferta concreta:

```text
Archetype → Vertical → OfferProfile versionado
```

A resolução segue `offer_profile_key` explícito, depois vertical, arquétipo e,
por fim, um perfil genérico. O resultado informa `resolved_from`, permitindo
auditar por que uma oferta foi escolhida. Campanhas sem `offer_profile_key`
continuam funcionando por compatibilidade com `target_service` e
`target_segment`.

## Contrato

```yaml
key: str
version: str
archetype: str
vertical: str
offer: {name, tagline}
icp: {company_sizes, segments, cnaes, exclusions, geography}
discovery: {providers, target_candidates, provider_budgets, query_strategy}
prescoring: {required_signals, weights, threshold, top_k, on_insufficient_data}
enrichment: {steps, stop_conditions, max_cost}
signals: {positive, negative, disqualifiers}
intent: {event_weights, decay, trigger_threshold}
decision_makers: {roles, buyer_types, priority}
channels: {priority}
qualification: {questions}
outreach: {angle, evidence_requirements}
```

Perfis padrão atuais:

| Key | Arquétipo | Vertical |
|---|---|---|
| `landing_page` | `web_presence` | `digital` |
| `mechanical_project` | `industrial` | `mechanical_engineering` |
| `technical_drawing` | `industrial` | `mechanical_engineering` |
| `machine_manual` | `industrial` | `mechanical_engineering` |
| `trophies` | `custom_products` | `awards` |

Para adicionar uma oferta hoje, altere
`services/workers/src/services/prospecting/default_profiles.py` e registre a
versão. Ainda não há CRUD administrativo, publicação transacional ou rollback.

## OfferMatcher e `LeadOpportunity`

O matcher percorre os perfis registrados, calcula aderência 0–100 a partir de
sinais e ICP, registra evidências e retorna várias oportunidades para o mesmo
lead. Desqualificadores zeram a oportunidade; ausência de evidência não é
convertida em fato.

O resultado é persistido por `LeadOpportunityService` na tabela
`lead_opportunities`, com upsert idempotente por `(lead_id, offer_key)` e
`offer_version`. A API expõe `GET /api/leads/{lead_id}/oportunidades`, sempre
com filtro pela organização do usuário.

```text
Lead
 ├─ Offer A / versão / score / evidências
 ├─ Offer B / versão / score / evidências
 └─ Offer C / versão / score / evidências
```

O snapshot JSONB legado em `Lead.evidence_score` permanece por compatibilidade;
`lead_opportunities` é a fonte relacional das oportunidades novas.

## Event Discovery e oferta

Event Discovery é operacional em `source=events`: coleta, valida, deduplica,
resolve o organizador, calcula timing e persiste `event_opportunities`. A
persistência aceita `offer_key` (default `trophies`) e vincula o organizador a
`Company`/`Lead` somente com evidência suficiente.

O fluxo executa `EventOpportunity → OfferMatcher → LeadOpportunity` e prepara
uma ação recomendada para eventos futuros com contato persistido. Ainda não
executa descoberta externa de decisor nem `→ outreach`; o envio permanece humano.

## Outcomes e versões

Conversões e outcomes persistidos carregam `offer_key`, `offer_version` e,
quando conhecido, `lead_opportunity_id`. `commercial_outcomes` alimenta
`GET /api/intelligence/outcomes`.

Comparações A/B são calculadas por `CommercialComparisonService` usando o
registry/comparador existente, intervalo de Wilson e amostra mínima. O
resultado é persistido em `commercial_comparisons`; aprovação conclusiva por
manager/owner registra versão, ator, evidência e auditoria. O módulo
`learning_metrics.py` ainda é in-memory por desenho do adaptador, mas o caminho
operacional lê e grava no PostgreSQL.

## Limitações e próximos passos

- Não há entidade administrativa para definir OfferProfiles sem deploy.
- Não há snapshot imutável de toda a configuração usada por cada lead nem
  política de re-scoring publicada.
- A resolução de decisores é best-effort e a migração completa para `Person`
  ainda não terminou.
- BI avançado por vertical, consultor, canal, campanha, variante e Precision@K
  ainda precisa de agregações e jobs próprios.

## Validação

O contrato é coberto por testes unitários/integrados de resolver, matcher,
persistência de oportunidades, outcomes e comparação A/B. O snapshot geral da
branch foi validado com 928 testes Python sob `-W error`, `compileall`, lint,
TypeScript, build Web e migration verifier no head `bb7c8d9e0f1a`.