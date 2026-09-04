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

---

## Fase C — OfferMatcher

> **Status:** ✅ COMPLETE (consolidação §Fase C).

Associa uma empresa a **múltiplas oportunidades simultâneas** (uma por
OfferProfile relevante), com score (0-100), evidência e cascata
rastreável.

### Critério da Fase C

> "Uma empresa pode possuir múltiplas oportunidades simultâneas."

Validado pelo test:
- Metalúrgica → 3 oportunidades (mechanical_project, technical_drawing, machine_manual)
- Clínica psicologia → 1+ oportunidade (landing_page)
- Federação que fabrica troféus → 2 (trophies + industrial)

### Algoritmo de score

```
score = min(100, (sinais_positivos_presentes / total_declarados) * 70
                  + min(30, icp_hits * 10))
```

- **Sinais positivos presentes**: cada um conta 70/total pontos
- **ICP hits**: segment + cnae + company_size, cada um conta 10 pontos (cap 30)
- **Disqualifiers**: zeram o score e marcam evidência

### `LeadOpportunity` (entidade conceitual)

```python
@dataclass(frozen=True)
class LeadOpportunity:
    offer_key: str
    profile_key: str
    score: int  # 0-100
    evidence: List[str]
    resolved_from: str  # explicit|vertical|archetype|generic
    signals_matched: List[str]
    signals_missing: List[str]
```

### Critério Fase C satisfeito

- [x] serviço (`OfferMatcher`)
- [x] score por oferta
- [x] evidência (`evidence` + `signals_matched/missing`)
- [x] testes (9 unit + 4 integration = 13)
- [x] múltiplas oportunidades simultâneas
- [x] to_dict/from_dict para persistência futura (`LeadOpportunity`)

### Próximos passos

- **PR 4** — DiscoveryProvider contract (Fase D) — executor real
- **PR 5** — IntentProvider contract (Fase E) — collector real
