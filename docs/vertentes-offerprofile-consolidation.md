# Vertentes × OfferProfile — mapa de consolidação (Fase A)

> Snapshot: branch `fix/fase-a-template-tenant-isolation` sobre a `main` em
> `aa52cdc` (merge do PR #169). Código + testes tratados como fonte de verdade;
> documentos antigos usados só como contexto.

Vocabulário: **Vertente** = `CampaignScoringTemplate` (linha em
`campaign_scoring_templates`, global quando `organization_id` é NULL, privada
quando preenchido; UI em `/configuracoes/vertentes`). **OfferProfile** = perfil
declarativo em código (`default_profiles.py` + overlay por workspace via
`OfferProfileVersion`/`build_effective_registry`).

## 1. Onde cada um influencia

| Etapa | Vertente influencia? | OfferProfile influencia? | Campos | Risco de divergência |
|---|---|---|---|---|
| Criação de campanha | Não (só `offer_profile_key` validado contra o registry global) | Sim (`offer_profile_key` explícito) | `Campaign.offer_profile_key` | Baixo hoje; validar contra registry efetivo é evolução (novo `key` publicado pelo tenant ainda não passa na validação) |
| Interpretação do brief (`from-brief`) | Sim (router exact→fuzzy→LLM→genérico; gera rascunho em `GENERATE_NEW`) | Sim (sugere `offer_profile_key/label/resolved_from`) | `target_service/segment` → ambos | **Alto (era)**: router sem escopo tenant escolhia vertente privada de outro workspace; corrigido nesta fatia |
| Discovery (planejamento) | Indireto via `prospecting_profile` derivado do template | Sim (providers, budgets, `target_candidates`, `query_strategy`) | `DiscoveryExecutor` + plano auditável | Médio: pipeline resolve oferta pelo registry **global**, ignorando o overlay publicado do workspace |
| Pre-scoring | Sim (`prescoring_config`: profile, threshold, top_k, weights, required_signals) | Sim (sobrescreve `prescoring` quando `resolved_from != generic`) | `prospecting_profile["prescoring"]` | Médio: duas fontes, precedência definida no `pipeline_worker` (oferta vence) mas implícita |
| Enrichment | Sim (`enrichment_steps`, `enrichment_strategy`) | Sim (`enrichment.steps`, stop, max_cost; sobrescreve steps) | `resolve_enrichment_steps` | Médio: mesma precedência implícita |
| Seleção de providers | Via steps do template | Via `discovery.providers/budgets` e `people_discovery` (max_cost, steps, role fit, gates) | quotas/opt-ins por org | Baixo: providers externos sempre opt-in por org |
| Scoring (IA) | Sim (sinais + instruções do template no prompt) | Parcial (perfil efetivo alimenta contexto; matcher é separado) | `scoring_service` + `derive_profile_key` | Médio: `derive_profile_key` lê o template, não o perfil resolvido |
| OfferMatcher | Não | Sim (signals positive/negative/disqualifiers, weights, ICP) | `lead_opportunities` + `score_breakdown` | Baixo |
| Criação de oportunidade | Via `campaign.scoring_template_id` (contexto) | Sim (`offer_key/version`, evidências) | `LeadOpportunityService` usa `build_effective_registry` (tenant-aware ✅) | Baixo |
| People discovery | Não | Sim (`decision_makers.roles/buyer_types`, `people_discovery.*`) | `ContactEnrichmentService`, waterfall | Baixo |
| Decisor (buyer role) | Não | Sim (`required_buyer_role`, fallback `buyer_types`, `BuyerPersona`) | snapshots + evidence | Baixo |
| Next best action | Indireto (roteabilidade do contato) | Indireto (canais do perfil em eventos `trophies`) | `NextBestActionService` | Baixo |
| Cadência | Sim (`cadence_schedule`: `[0,3,7,14]` default, ciclos longos industriais) | Não | `schedule_cadence`, `_normalize_cadence_days` | Baixo (fonte única: template) |
| Sequences/playbook/mensagens | Sim (`playbook`: hooks, subjects, objeções, `stage_angles`) | Sim (`outreach.angle`, `evidence_requirements`) | `get_playbook_for_campaign`, `OutreachService` | **Alto**: dois playbooks/ângulos concorrentes sem precedência documentada |
| Analytics | Sim (sugestão de calibração da vertente por frequência) | Sim (cortes por oferta/versão, Precision@K, providers) | `analytics_service`, outcomes | Médio: feedback de utilidade (#169) ainda não alimenta nenhum dos dois |
| Learning | Sim (`scoring_feedback`/`template_learning` por template) | Sim (comparação A/B → proposta → publicação → `OfferProfileVersion` por org) | tabelas distintas | **Alto**: dois loops de aprendizado paralelos sobre o mesmo ranking |
| Versionamento/rollback | Não (edição in-place; `is_generated`, `is_active`) | Sim (versões por workspace, single-active, rollback exato) | `ControlledLearningService` | Médio: vertente não tem histórico; reverter edição é impossível |

## 2. Duplicação semântica

| Campo/conceito | Classificação | Motivo |
|---|---|---|
| Positive/negative/context signals | Deve pertencer a **OfferProfile** | `signals.*` + `signals.weights` já ponderam no matcher; sinais do template em linguagem livre alimentam só o prompt da LLM |
| ICP (portes, segmentos, CNAEs, exclusões, geografia) | Deve pertencer a **OfferProfile** | Template não tem ICP estruturado; `context_signals` livre é substituto fraco |
| Buyer persona/decision makers | Deve pertencer a **OfferProfile** | `decision_makers` + `BuyerPersona` já operam com gates; template não cobre |
| Timing/janela comercial | Deve pertencer a **OfferProfile** | `intent.*` + `EventTimingScorer`; template não cobre |
| Weights/thresholds de scoring | Deve pertencer a **OfferProfile** (via learning versionado) | `template_learning` ajusta sem versão/rollback; loop controlado já existe para oferta |
| Provider strategy/budgets | Deve pertencer a **OfferProfile** | `discovery.*` + `people_discovery.*` declarativos; template só tem steps |
| Pre-scoring | **Derivado** (perfil resolvido) | Hoje nasce do template e é sobrescrito pela oferta — inverter: resolver oferta primeiro, derivar pre-scoring dela |
| Enrichment strategy | **Derivado** (perfil resolvido) | Mesmo caso do pre-scoring |
| Cadence (`cadence_schedule`) | **Estratégia operacional** (fica na Vertente) | Ciclo de follow-up é operacional, não definição comercial; nenhuma contraparte na oferta |
| Playbook/messaging | **Estratégia operacional** (fica na Vertente), com `outreach.angle` como diretriz da oferta | Manter um único ponto de edição; ângulo vem da oferta, redação fica na vertente |
| `requires_technical_report/business_data`, `enrichment_steps` | **Legado temporário** | Compatibilidade com scoring legado; migrar consumidores para `offer.enrichment.steps` |
| `extra_instructions` | **Legado temporário** | Prompt livre sem contraparte versionada; absorver em `qualification`/`outreach` da oferta |
| `service_label` × `offer.key/name` | **Duplicação perigosa** | Dois namespaces de "oferta" sem vínculo; brief resolve os dois por regras diferentes |

## 3. Auditoria tenant isolation (`CampaignScoringTemplate`)

Achados desta fatia (todos com prova negativa em
`tests/test_template_tenant_isolation.py`):

1. `template_router._templates_snapshot` sem filtro de org — exact, fuzzy,
   classificação LLM e fallback genérico operavam sobre o pool global,
   incluindo privadas de outros workspaces. **Corrigido**: `_visible_clause`
   (global OU própria org) em snapshot, exact, fuzzy, genérico, lookup por ID
   explícito e re-lookup do label escolhido pela LLM. Sem org (chamadas
   legadas), comportamento anterior preservado.
2. `POST /campaigns/from-brief`: re-lookup por `service_label` sem escopo —
   preview de B vinculava a privada de A. **Corrigido** (filtro visível +
   própria-org-primeiro).
3. `pipeline_worker`: vínculo pós-geração por label sem escopo. **Corrigido**
   (mesmo padrão).
4. `PATCH /scoring-templates/{id}`: checagem global de conflito de nome —
   409 revelava existência de vertente privada alheia e travava renomeação
   legítima. **Corrigido** (só escopo visível).
5. `TemplateGenerationService._load_generic`: "Genérico" sem escopo (uma
   privada chamada "Genérico" sequestraria o fallback). **Corrigido**.
6. `leads.py`: 4 leituras de `Campaign` via `lead.campaign_id` sem filtro de
   org (pitch, mensagens, playbook LinkedIn, cadência). **Corrigido**.
7. Já isolados (verificados, sem mudança): list/get por ID, create (sempre na
   própria org), duplicate via `source_template_id`, delete (só própria org,
   globais protegidas), patch de globais bloqueado, vínculo explícito no
   `PATCH /campaigns`.

Risco residual conhecido (não desta fatia): o pipeline resolve OfferProfile
pelo registry **global** (`pipeline_worker`, `enrichment_orchestrator`,
`event_opportunity_service`, `contact_enrichment_service`); só
`LeadOpportunityService` usa `build_effective_registry`. Versões publicadas
pelo workspace ainda não governam discovery/scoring — sem vazamento entre
workspaces (catálogo global é igual para todos), mas publicação sem efeito é
a próxima divergência a fechar.

## 4. Direção arquitetural

```text
OfferProfile            ← definição comercial (ICP, signals, personas,
                          matcher, timing, learning, golden patterns)
└── ProspectingStrategy ← pre-scoring, discovery/enrichment, providers,
                          cadência, playbook, instruções operacionais
Vertente = camada amigável de configuração da oferta/estratégia
(não: segundo sistema paralelo)
```

## 5. Compatibilidade e migração incremental

1. Esta fatia: só hardening tenant + testes; nenhum comportamento removido.
2. Resolver oferta primeiro no pipeline e derivar `prospecting_profile` dela;
   template vira override explícito auditável (precedência documentada).
3. Unificar `service_label`↔`offer.key` com vínculo explícito campanha↔oferta
   (já existe `offer_profile_key`; faltam telas e validação contra o registry
   efetivo).
4. Migrar `playbook`/`cadence_schedule` para `ProspectingStrategy` referenciada
   pelo perfil; UI de Vertentes passa a editar a estratégia da oferta.
5. Unificar loops de learning (`scoring_feedback` como evidência do controlled
   learning, nunca ajuste direto).
6. Só então depreciar campos legados do template, com telemetria de uso de
   fallback (P1.5).

Ordem recomendada: 2 → 3 → 4 → 5 → 6. Cada passo em PR pequeno com gates
verdes no HEAD final. Nenhum passo remove `CampaignScoringTemplate` antes de
cobertura total pelo perfil efetivo.
