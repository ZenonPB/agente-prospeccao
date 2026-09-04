# OfferProfile — entidade central de inteligência comercial

> **Status:** ✅ COMPLETE (Fase B do plano de consolidação).
> **Branch:** `fixes-fase3`
> **Implementação:** `services/workers/src/services/prospecting/`

Substitui mappings hardcoded espalhados (`ICP_BY_PROFILE`, `ROLE_BY_PROFILE`,
`TRIGGER_BY_PROFILE`, `WEIGHTS_BY_PROFILE`) por uma única entidade
declarativa **versionada** que representa uma oferta comercial completa.

## Arquitetura

```
Archetype  (fallback genérico: web_presence, business_opportunity, industrial)
   ↓
Vertical  (contexto de mercado: digital, industrial, custom_products)
   ↓
OfferProfile  (unidade principal — versão declarativa completa)
```

## Cascata de resolução

```
explicit offer_profile_key
       ↓ fallback
vertical_key
       ↓ fallback
archetype_key
       ↓ fallback
generic
```

Consolidação §3.5: campanhas antigas continuam funcionando.

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

## Profiles iniciais (5)

| Key | Archetype | Vertical | Decisão |
|---|---|---|---|
| `landing_page` | web_presence | digital | ausencia de site = publico-alvo |
| `mechanical_project` | industrial | mechanical_engineering | CNAE + porte |
| `technical_drawing` | industrial | mechanical_engineering | desenho sob demanda |
| `machine_manual` | industrial | mechanical_engineering | NR-12 / documentação |
| `trophies` | custom_products | awards | eventos sazonais (decay 30d) |

## Adicionar nova oferta

1. Adicionar entry em `services/workers/src/services/prospecting/default_profiles.py`
2. **Nada precisa mudar em engine/pipeline** (consolidação §Fase B critério)

## Status do DoD

- [x] contrato definido (dataclass frozen + dict roundtrip)
- [x] implementação não-placeholder
- [x] integrado ao pipeline (via `OfferProfileResolver.resolve()`)
- [x] configuração/versionamento (`version` por profile)
- [x] evidência/proveniência (`resolved_from` indica cascata usada)
- [x] diferencia erro/ausência/desconhecido (cascata cai no `generic`)
- [x] unit tests (16 tests, 0.03s)
- [x] integration test (5 profiles iniciais instanciados)
- [x] cenário realista (3 ofertas industriais distintas no mesmo vertical)
- [x] observabilidade (`resolved_from` retornado)
- [x] documentação corresponde ao código
- [x] sem mapping hardcoded que deveria ser config

## Mapa de capabilities atualizado

| Capability | Status | Entry point | Tests |
|---|---|---|---|
| `offer_profile.dataclass` | ✅ COMPLETE | `services/prospecting/offer_profile.py` | 6 |
| `offer_profile.registry` | ✅ COMPLETE | `services/prospecting/offer_profile.py` | 3 |
| `offer_profile.resolver` | ✅ COMPLETE | `services/prospecting/offer_profile.py` | 4 |
| `offer_profile.defaults` | ✅ COMPLETE | `services/prospecting/default_profiles.py` | 5 |
