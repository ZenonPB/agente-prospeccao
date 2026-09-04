# Diagnóstico e Fase 1 — Fundação de pre-scoring e perfil de prospecção

> **Status: ✅ Fase 1 entregue (parcial em relação ao pacote completo).**
> Diagnóstico baseado no código real do branch `main` (pré-implementação),
> não apenas nos docs de melhoria.

## Estado atual (mapeamento real)

| Etapa | Arquivo | Observação |
|---|---|---|
| Coleta Places/CNAE/CSV | `services/api/src/pipeline_worker.py` (`run_pipeline`) | dedupe in-batch por `place_id`/domínio (`filter_new_batch_items`) |
| Template router | `services/workers/src/services/template_router.py` | exact → fuzzy → LLM → Genérico; `GENERATE_NEW` → `TemplateGenerationService` |
| Enrichment | `services/workers/src/services/enrichment_orchestrator.py` | `resolve_enrichment_steps` já é ativação declarativa por template |
| Scoring | `services/workers/src/services/scoring_service.py` | Groq; `score_factors`/`evidence` JSONB; threshold por org |
| Contatos | `contact_enrichment_service.py` | só QUALIFICADOS (fase 3 automática) |
| Learning | `learning_compilation_service.py` + score feedback | regras de calibração por template/org |

## O que já cobria parcialmente os novos docs

- `CampaignScoringTemplate` (sinais + `enrichment_steps` + flags) ≈ proto-ProspectingProfile (docs 17/31).
- `enrichment_steps` ≈ proto-capability-registry (doc 21), com fallback por flags binários.
- `score_factors`/`evidence` ≈ proto-Signal Registry (doc 20), mas sem `source`/`confidence`/`observed_at`/epistemic status.
- `AnalysisProfile` (WEB_PRESENCE × BUSINESS_OPPORTUNITY) já separa caminhos com/sem site.

## O que estava duplicado/acoplado

- Regex/labels de vertical hardcoded no core do scoring (`_WEB_PRESENCE_LABELS`, `_ERP_WEBAPP_LABELS`) — mantidos (fix recente de falso-positivo ERP); a fundação permite migrá-los para config depois.
- Empresa encontrada virava `Lead` imediatamente: **todo candidato coletado consumia enriquecimento caro** (docs 01/06/07 não suportados).
- Template só era resolvido DEPOIS da criação dos leads — impossibilitava gate no discovery.
- Ordem de enrichment fixa (definida só por ativação, não por sequência da oferta).

## Decisões da fase 1

1. **Sem tabela `Candidate`** (doc 06 manda começar lógico): Candidate = item de coleta pré-promoção; gate decide a promoção. Idempotência de promoção não se aplica (descartado não persiste). Reavaliar tabela real quando houver métricas de retrieval/early stopping.
2. **Perfil via configuração, não código**: `resolve_prospecting_profile` deriva o perfil da composição de `enrichment_steps` do template (config já existente) com override explícito em `prescoring_config.profile`. Engine não contém `if vertical == ...`.
3. **Gate desligado por padrão** em código; ativado por template (`prescoring_config.enabled`). Seeds ativam com thresholds conservadores para Sites (45), ERP (40) e Engenharia (25).
4. **Score vetorial como contrato opcional**: `leads.score_vector` (JSONB) ao lado do `qualification_score` legado, que continua fonte de verdade do funil. Dimensões ainda não geradas pela LLM — contrato pronto para evolução.
5. **Pre-scoring 100% FACT**: sinais de discovery carregam `{key, value, source, confidence, observed_at, evidence, epistemic:"FACT"}` — embrião do Signal Registry (doc 20).

## Implementado (fase 1)

- `prospecting_profile_service.py` — resolução centralizada do perfil + pesos/threshold default por perfil.
- `candidate_pre_scoring_service.py` — pré-ranking determinístico sem LLM + `select_candidates` (gate com top_k, ordenação estável, stats).
- Migration `a7b8c9d0e1f2` — `campaign_scoring_templates.prescoring_config` + `leads.score_vector`.
- `pipeline_worker.py` — routing hoisted para antes da coleta; gate na promoção; `prescoring_discarded` no summary do job/WS.
- `_persist_scoring`/`_normalize_response` — score_vector persistido quando presente (clamp 0–100, `overall` derivado, `formula_version`).
- Seeds com `prescoring_config` por vertical; API expõe `score_vector` no detalhe.
- 25 testes novos (`test_candidate_pre_scoring.py`, `test_prospecting_profile.py`, `test_prescoring_gate.py`, `test_score_vector.py`).

## O que NÃO foi implementado (fases seguintes)

- ~~Candidatos descartados sem auditoria~~ → **corrigido na revisão** (tabela `prescoring_discards`, migration `f1a2b3c4d5e6`); falta endpoint/painel de leitura.
- Métricas de retrieval e rastreabilidade completa de descartes (doc 12) — base pronta na tabela de descartes.
- Ordem condicional de enrichment (doc 08 além da ativação atual) e capability registry completo (doc 21).
- Dimensões de score produzidas pela LLM/pipeline (doc 02: need/icp_fit/intent...), Intent Engine (doc 19/24).
- ProspectingProfile como entidade versionável com discovery/outreach/decision-maker strategy (docs 17/22/25).
- Migração das regex de vertical do `scoring_service` para config (requer revalidação dos fixes recentes de scoring).
