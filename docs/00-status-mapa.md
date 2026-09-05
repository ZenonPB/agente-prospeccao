# Mapa de status — pacote de melhorias + consolidação

> **Snapshot:** 2026-09-04 · branch `fixes-fase3` · consolidação operacional pós-Fases C–H
>
> Este arquivo é a **fonte única de verdade** para entender o que está
> completo, parcial ou apenas declarado. Reflete callers, persistência,
> providers e testes do código real — não apenas a existência de um arquivo.

## Legenda

| Marca | Significado |
|---|---|
| ✅ **COMPLETE** | Código + testes + consumidor operacional + persistência/provider quando aplicável. |
| 🟠 **PARTIAL** | Parte operacional, mas falta uma condição relevante do DoD. |
| 🔵 **SCAFFOLDING** | Interface/helper ou provider sem operação real. |
| 🟡 **PROPOSED** | Apenas especificação, sem implementação. |

## Consolidação — Capability Matrix

| # | Capability | Status | Entry point | Tests | Provider real? |
|---|---|---|---|---|---|
| 1 | Candidate Pre-Scoring | ✅ COMPLETE | `services/candidate_pre_scoring_service.py` | ✅ | internal |
| 2 | Opportunity Score Vector v1 | ✅ COMPLETE | `services/scoring_service.py:282` | ✅ | Groq LLM |
| 3 | Template Landing Pages | ✅ COMPLETE | `seeds/scoring_templates.py` | ✅ | internal |
| 4 | Places Multi-Query | ✅ COMPLETE | `services/discovery_multi_query.py` | ✅ | internal |
| 5 | Search Query Generation | ✅ COMPLETE | `services/search_query_generation_service.py` | ✅ 7 | LLM optional + templates |
| 6 | Candidate vs Lead | ✅ COMPLETE | `services/candidate_pre_scoring_service.py` | ✅ | internal |
| 7 | Budgeted Enrichment | ✅ COMPLETE | `enrichment_capability_registry.py` | ✅ | internal |
| 8 | Enrichment Order by Service | ✅ COMPLETE | `enrichment_capability_registry.py:plan_enrichment_run` | ✅ | internal |
| 9 | Rating Count by Vertical | ✅ COMPLETE | `services/prospecting_profile_service.py:interpret_rating_count` | ✅ | internal |
| 10 | Niche Prior Learning | 🟠 PARTIAL | `services/learning_service.py:compute_niche_prior` | ✅ 11 | internal; sem caller comercial ativo |
| 11 | Learning from Sales Outcomes | 🟠 PARTIAL | `services/learning_service.py:record_outcome` | ✅ 11 | endpoint/evento de outcome ainda não conectado |
| 12 | Precision@K | 🟠 PARTIAL | `services/learning_service.py:precision_at_k` | ✅ 11 | função disponível; sem job/BI operacional |
| 13 | Chain Detection | ✅ COMPLETE | `services/chain_detection_service.py` | ✅ 6 | internal |
| 14 | Decision Maker Accessibility | ✅ COMPLETE | `scoring_service.py:VECTOR_WEIGHTS.dma` | ✅ | internal |
| 15 | Golden Lead Patterns | 🟠 PARTIAL | `services/learning_service.py:match_golden_patterns` | ✅ 11 | função disponível; sem consumidor no pipeline |
| 16 | Why Prospect Card | ✅ COMPLETE | `routes/leads.py:_lead_summary` | ✅ | internal |
| 17 | Prospecting Profile | ✅ COMPLETE | `services/prospecting_profile_service.py` | ✅ | internal |
| 18 | Universal Prospecting Questions | ✅ COMPLETE | `services/universal_prospecting_questions_service.py` | ✅ 10 | internal |
| 19 | ICP vs Intent | ✅ COMPLETE | `services/buying_trigger_service.py:icp_vs_intent` | ✅ 7 | internal |
| 20 | Signal Registry | ✅ COMPLETE | `services/signal_registry.py` | ✅ | internal |
| 21 | Enrichment Capability Registry | ✅ COMPLETE | `enrichment_capability_registry.py` | ✅ | internal |
| 22 | Discovery Planner | 🟠 PARTIAL | `services/discovery_planner_service.py:plan_enrichment_run` | ✅ 9 | plano é calculado/logado; executor ainda não dirige a coleta |
| 23 | CNAE as Discovery Provider | ✅ COMPLETE | `services/cnae_discovery_service.py` | ✅ | BrasilAPI/Receita |
| 24 | Intent Engine | 🟠 PARTIAL | `services/intent_engine_service.py` | ✅ 7 | engine existe; sem producer/job real conectado |
| 25 | Decision Maker Strategy | ✅ COMPLETE | `services/decision_maker_strategy_service.py` | ✅ 7 | internal |
| 26 | Buying Trigger | ✅ COMPLETE | `services/buying_trigger_service.py` | ✅ 7 | internal |
| 27 | Opportunity Vector v2 | ✅ COMPLETE | `scoring_service.py:VECTOR_V2_DIMS` | ✅ | internal |
| 28 | Prospecting Hypothesis | ✅ COMPLETE | `services/prospecting_hypothesis_service.py` | ✅ 8 | internal |
| 29 | Epistemic Status | ✅ COMPLETE | `signal_registry.py` | ✅ | internal |
| 30 | Discovery Questions | ✅ COMPLETE | `services/universal_prospecting_questions_service.py:discovery_questions_for` | ✅ 10 | internal |
| 31 | Vertical Pack | ✅ COMPLETE | `services/prospecting_hypothesis_service.py:vertical_pack_for` | ✅ 8 | internal |
| 32 | Archetypes as Fallback | ✅ COMPLETE | `services/archetype_service.py` | ✅ 6 | internal |
| 33 | Three-Level Learning | ✅ COMPLETE | `services/learning_service.py:ThreeLevelLearning` | ✅ 11 | internal |
| 34 | Decision Maker Resolution Pipeline | ✅ COMPLETE | `services/decision_maker_pipeline_service.py` | ✅ 7 | internal |
| 35 | People Discovery Service | ✅ COMPLETE | `services/contact_enrichment_service.py` | ✅ | Hunter + Receita |
| 36 | QSA Decision Makers | ✅ COMPLETE | `services/contact_provider_registry.py:classify_qsa_role` | ✅ 16 | Receita (QSA real) |
| 37 | Person Database Provider | ✅ COMPLETE | `services/contact_provider_registry.py` | ✅ 16 | Hunter (auto-register) |
| 38 | Email Finder after Identity | ✅ COMPLETE | `services/contact_provider_registry.py` | ✅ 16 | Hunter + heuristic |
| 39 | Email Pattern Inference | ✅ COMPLETE | `services/contact_provider_registry.py:infer_email_pattern` | ✅ 16 | internal (acentos) |
| 40 | Contact Confidence Score | ✅ COMPLETE | `services/contact_enrichment_service.py:confidence` | ✅ | internal |
| 41 | Channel Priority by Vertical | ✅ COMPLETE | `services/decision_maker_strategy_service.py:CHANNEL_PRIORITY` | ✅ 7 | internal |
| 42 | Routable Contact | ✅ COMPLETE | `services/routable_contact_service.py` | ✅ 7 | internal |
| 43 | Multiple Buyers | ✅ COMPLETE | `services/decision_maker_pipeline_service.py` | ✅ 7 | internal |
| 44 | Cascade Contact Search | ✅ COMPLETE | `services/contact_provider_registry.py:cascade_contact_search` | ✅ 16 | internal |
| 45 | Company Identity Resolver | ✅ COMPLETE | `services/company_person_service.py` | ✅ | internal |
| 46 | Domain-First Person Search | ✅ COMPLETE | `services/contact_provider_registry.py:domain_first_person_search` | ✅ 16 | internal |
| 47 | Actionable Contact Rate | ✅ COMPLETE | `services/routable_contact_service.py:actionable_contact_rate` | ✅ 7 | internal |

## Resumo executivo

- **Total:** 47 capabilities históricas + OfferProfile/OfferMatcher/Event/Intent/Learning
- **✅ COMPLETE:** capacidades históricas com cobertura operacional comprovada
- **🟠 PARTIAL:** coletores externos permanecem opt-in; resolução de decisores ainda mantém snapshot JSONB legado além dos contatos canônicos
- **🔵 SCAFFOLDING:** `learning_metrics.py` in-memory continua disponível para comparação offline; o endpoint operacional usa `commercial_outcomes`
- **Validação atual:** suíte Python completa, compilação dos serviços, lint/tsc/build do Web e migrations aplicadas no Postgres local

## Auditoria final — evidência operacional

| Capability | Status real | Entry point | Consumidor de produção | Persistência | Limitação conhecida |
|---|---|---|---|---|---|
| OfferProfile/Resolver | ✅ COMPLETE | `services/prospecting/offer_profile.py` | `pipeline_worker` resolve oferta explícita e campanhas legadas | oferta/versionamento no contexto + campaign.offer_profile_key | perfis customizados ainda são cadastrados em código |
| OfferMatcher | ✅ COMPLETE | `services/prospecting/offer_matcher.py` | `enrichment_orchestrator` pós-scoring | `lead_opportunities` + snapshot JSONB compatível | sem tela de gestão dedicada; detalhe do lead já exibe |
| DiscoveryProvider/Executor | ✅ COMPLETE | `services/prospecting/discovery_executor.py` | `pipeline_worker` usa `execute_async` para Places/CNAE declarativos | logs do job + provenance dos candidatos | providers sem credencial são pulados explicitamente |
| IntentProvider/Scorer | 🟠 PARTIAL | `services/prospecting/intent_provider.py` | `enrichment_orchestrator` usa HTML cacheado e jobs fornecidos no contexto | `lead.evidence_score.phase3` | job board externo precisa fornecer `scoring_data.jobs` |
| Event Discovery | 🟠 PARTIAL | `services/prospecting/event_discovery.py` | `pipeline_worker` via `source=events` | `event_opportunities` + `/api/intelligence/events` | endpoint externo é opt-in via `EVENT_DISCOVERY_URL` |
| Decision Maker Resolution | 🟠 PARTIAL | `services/prospecting/decision_maker_resolution.py` | `ContactEnrichmentService` | `lead.evidence_score.phase3_contact` | resolução é best-effort; `PersonContact` não é persistido diretamente |
| Learning/Metrics | 🟠 PARTIAL | `services/prospecting/commercial_outcome_service.py` | conversão/status real + `/api/intelligence/outcomes` | `commercial_outcomes` | dashboard dedicado e comparação A/B SQL ainda pendentes |

### Verificações executadas

- `graphify update . --no-cluster`: grafo atualizado com 5.508 nós e 13.047 arestas.
- `python -m pytest tests -q`: 889 testes passaram; o E2E original continua condicionado a `E2E_DATABASE_URL`.
- `python -m compileall -q services/api services/workers`: passou.
- `npm run lint`, `npx tsc --noEmit` e `npm run build`: passaram nas validações desta consolidação.
- Alembic: head `fc2d3e4f5a6b`, com `lead_opportunities`, `offer_profile_key`, `event_opportunities`, `commercial_outcomes` e versionamento aplicados.

## Próximas ações obrigatórias

1. Configurar e validar um provider externo de eventos em ambiente controlado.
2. Adicionar um job opt-in para coletar vagas e alimentar `IntentProvider`.
3. Promover `commercial_outcomes` ao dashboard de BI com comparação SQL por versão.
4. Persistir `PersonContact` como entidade canônica de decisor, mantendo o snapshot legado durante a migração.
5. Rodar o E2E original com `E2E_DATABASE_URL` e credenciais de teste controladas.
