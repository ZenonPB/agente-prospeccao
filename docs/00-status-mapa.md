# Mapa de status — pacote de melhorias + consolidação

> **Snapshot:** 2026-09-04 · branch `fixes-fase3` · auditoria final pós-Fases C–H
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
- **🟠 PARTIAL:** OfferProfile ainda não é a fonte do pipeline; Event Discovery não tem provider externo configurado; LearningMetrics não persiste no PostgreSQL/BI
- **🔵 SCAFFOLDING:** adapters sem credencial/provider real e componentes sem consumidor de produção
- **Testes focados pós-auditoria:** 161 anteriores + regressões desta auditoria; a suíte global exige `requirements-dev.txt` e banco no e2e

## Auditoria final — evidência operacional

| Capability | Status real | Entry point | Consumidor de produção | Persistência | Limitação conhecida |
|---|---|---|---|---|---|
| OfferProfile/Resolver | 🟠 PARTIAL | `services/prospecting/offer_profile.py` | testes e import; `pipeline_worker` ainda usa `CampaignScoringTemplate`/`resolve_prospecting_profile` | nenhuma tabela própria | resolver de oferta ainda não é a fonte única do pipeline |
| OfferMatcher | 🟠 PARTIAL | `services/prospecting/offer_matcher.py` | `enrichment_orchestrator` | JSONB `evidence_score` | não há tabela `lead_opportunities`; registry default em código |
| DiscoveryProvider/Executor | 🟠 PARTIAL | `services/prospecting/discovery_executor.py` | executor testado; `pipeline_worker` ainda chama Places diretamente | logs/evento do job | adapters reais não são usados pelo pipeline |
| IntentProvider/Scorer | 🟠 PARTIAL | `services/prospecting/intent_provider.py` | nenhum job de produção | nenhuma | jobs/website precisam ser alimentados por coletores reais |
| Event Discovery | 🔵 SCAFFOLDING | `services/prospecting/event_discovery.py` | nenhum caller de produção | nenhuma | `SportsFederationProvider` é cadastro injetado/stub, não coletor externo |
| Decision Maker Resolution | 🟠 PARTIAL | `services/prospecting/decision_maker_resolution.py` | `ContactEnrichmentService` | `lead.evidence_score.phase3_contact` | resolução é best-effort; `PersonContact` não é persistido diretamente |
| Learning/Metrics | 🔵 SCAFFOLDING | `services/prospecting/learning_metrics.py` | nenhum endpoint/job | somente memória | não mede dados reais nem alimenta dashboard |

### Verificações executadas

- `graphify extract --code-only`: grafo gerado com 4.893 nós e 11.045 arestas.
- Testes focados C–H + regressões: passaram com `-W error`.
- `python -m py_compile`: arquivos alterados sem erro.
- E2E original de outreach: **skipped** sem `E2E_DATABASE_URL`; não é evidência de E2E verde.
- Alembic: migration `e8f9a0b1c2d3` cria `notifications` e está aplicada no banco local; `alembic check` ainda reporta divergências históricas de metadata/índices que não pertencem a esta correção.

## Próximas ações obrigatórias

1. Fazer `OfferProfileResolver` ser a fonte única para o `pipeline_worker`.
2. Fazer `DiscoveryExecutor.execute_async` consumir o plano real no pipeline.
3. Criar migrations/tabelas para `LeadOpportunity`, `EventOpportunity` e outcomes.
4. Implementar collectors externos opt-in para jobs, eventos e organizadores.
5. Expor métricas persistidas por oferta/provider/version no endpoint de analytics.
6. Rodar o E2E original com PostgreSQL atualizado (`alembic upgrade head`).
