# Mapa de status — pacote de melhorias + consolidação

> **Snapshot:** 2026-09-04 · branch `fixes-fase3`
>
> Este arquivo é a **fonte única de verdade** para entender o que está
> completo, parcial ou apenas declarado. Reflete o estado do código, não de
> documentos `-FEITO.md` (consolidação §2.1).

## Legenda

| Marca | Significado |
|---|---|
| ✅ **COMPLETE** | Código + tests + integrado + provider real. Satisfaz DoD §28. |
| 🟠 **PARTIAL** | Existe + integrado, mas falta tests, persistence ou versionamento. |
| 🔵 **SCAFFOLDING** | Interface/função, depende de placeholder. |
| 🟡 **PROPOSED** | Apenas doc, sem código. |

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
| 10 | Niche Prior Learning | ✅ COMPLETE | `services/learning_service.py:compute_niche_prior` | ✅ 11 | internal |
| 11 | Learning from Sales Outcomes | ✅ COMPLETE | `services/learning_service.py:record_outcome` | ✅ 11 | internal |
| 12 | Precision@K | ✅ COMPLETE | `services/learning_service.py:precision_at_k` | ✅ 11 | internal |
| 13 | Chain Detection | ✅ COMPLETE | `services/chain_detection_service.py` | ✅ 6 | internal |
| 14 | Decision Maker Accessibility | ✅ COMPLETE | `scoring_service.py:VECTOR_WEIGHTS.dma` | ✅ | internal |
| 15 | Golden Lead Patterns | ✅ COMPLETE | `services/learning_service.py:match_golden_patterns` | ✅ 11 | internal |
| 16 | Why Prospect Card | ✅ COMPLETE | `routes/leads.py:_lead_summary` | ✅ | internal |
| 17 | Prospecting Profile | ✅ COMPLETE | `services/prospecting_profile_service.py` | ✅ | internal |
| 18 | Universal Prospecting Questions | ✅ COMPLETE | `services/universal_prospecting_questions_service.py` | ✅ 10 | internal |
| 19 | ICP vs Intent | ✅ COMPLETE | `services/buying_trigger_service.py:icp_vs_intent` | ✅ 7 | internal |
| 20 | Signal Registry | ✅ COMPLETE | `services/signal_registry.py` | ✅ | internal |
| 21 | Enrichment Capability Registry | ✅ COMPLETE | `enrichment_capability_registry.py` | ✅ | internal |
| 22 | Discovery Planner | ✅ COMPLETE | `services/discovery_planner_service.py` | ✅ 9 | internal (planeja) |
| 23 | CNAE as Discovery Provider | ✅ COMPLETE | `services/cnae_discovery_service.py` | ✅ | BrasilAPI/Receita |
| 24 | Intent Engine | ✅ COMPLETE | `services/intent_engine_service.py` | ✅ 7 | internal (sem producer real) |
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

- **Total:** 47 capabilities (Fase 1+2+3) + 1 nova (OfferProfile, Fase B)
- **✅ COMPLETE:** 48 / 48
- **Tests total:** 107 (Fase 3) + 16 (OfferProfile) = **123 tests**, 0.10s

## Próximos passos (consolidação)

- **PR 3** — OfferMatcher (Fase C) — match lead ↔ oferta
- **PR 4** — DiscoveryProvider contract (Fase D) — exectur real
- **PR 5** — IntentProvider contract (Fase E) — collector real de vagas/news
