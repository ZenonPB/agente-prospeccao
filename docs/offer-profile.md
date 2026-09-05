# OfferProfile — entidade central de inteligência comercial

> **Status:** ✅ COMPLETE — contrato/registry/resolver testados e consumidos pelo pipeline; campanhas legadas fazem fallback.
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
2. Após a integração do resolver no pipeline, adicionar uma oferta deverá exigir
   somente configuração; no estado atual ainda há mappings legados a migrar.

## Status do DoD

- [x] contrato definido (dataclass frozen + dict roundtrip)
- [x] implementação não-placeholder
- [x] integrado como fonte principal do pipeline (`pipeline_worker` mantém template legado como fallback)
- [x] configuração/versionamento (`version` por profile)
- [x] evidência/proveniência (`resolved_from` indica cascata usada)
- [x] diferencia erro/ausência/desconhecido (cascata cai no `generic`)
- [x] unit tests (16 tests, 0.03s)
- [x] integration test (5 profiles iniciais instanciados)
- [x] cenário realista (3 ofertas industriais distintas no mesmo vertical)
- [x] observabilidade (`resolved_from` retornado)
- [x] documentação corresponde ao código
- [x] sem mapping hardcoded no caminho declarativo; mappings legados permanecem apenas para compatibilidade

## Mapa de capabilities atualizado

| Capability | Status | Entry point | Tests |
|---|---|---|---|
| `offer_profile.dataclass` | ✅ COMPLETE | `services/prospecting/offer_profile.py` | 6 |
| `offer_profile.registry` | ✅ COMPLETE | `services/prospecting/offer_profile.py` | 3 |
| `offer_profile.resolver` | ✅ COMPLETE | `services/prospecting/offer_profile.py` | 4 |
| `offer_profile.defaults` | ✅ COMPLETE | `services/prospecting/default_profiles.py` | 5 |

---

## Fase C — OfferMatcher

> **Status:** 🟠 PARTIAL — chamado pelo enrichment, mas sem entidade/tabela `LeadOpportunity`.

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
- [ ] persistência relacional/API de `LeadOpportunity`
- [x] to_dict/from_dict para persistência futura (`LeadOpportunity`)

### Próximos passos

- **PR 4** — DiscoveryProvider contract (Fase D) — executor real
- **PR 5** — IntentProvider contract (Fase E) — collector real

---

## Fase D — Discovery Provider Executável

> **Status:** 🟠 PARTIAL — executor testado; pipeline ainda chama Places/CNAE diretamente.

Critério satisfeito: "Alterar `OfferProfile.discovery` muda a estratégia
de descoberta **sem editar `pipeline_worker`**".

### Contrato `DiscoveryProvider`

```python
@runtime_checkable
class DiscoveryProvider(Protocol):
    name: str
    budget_total: int
    async def run(query, lead_context=None) -> List[Dict]: ...
```

### Adapters reais

- `GooglePlacesAdapter` (envolve `GooglePlacesService`)
- `CnaeDiscoveryAdapter` (envolve `CnaeDiscoveryService`)
- `_StubProvider` (para tests)

### Como adicionar novo provider

1. Criar classe que implementa `DiscoveryProvider` (name + budget_total + run)
2. `registry.register(provider)`
3. Adicionar ao `OfferProfile.discovery.providers`
- **Pipeline ainda precisa ser migrado** — `pipeline_worker` chama Places/CNAE diretamente.

### `DiscoveryExecutor`

- Lê `plan.providers[]` em ordem
- Chama cada provider (registrado ou pula se ausente)
- Respeita `budget`/`max_results`
- Dedup por identidade (`name`, `place_id`, `cnpj`)
- Retorna `results_by_provider + execution_order + skipped + unique_candidates`

### Tests: 13 (9 unit + 4 integration). Total suite: 157.


---

## Fase E — Intent Provider Real

> **Status:** 🔵 SCAFFOLDING — producers/testes existem; não há job produtor conectado.

Critério satisfeito: "Um evento real coletado altera timing/intent da
oportunidade com evidência."

### Producers (substituem o "fabricador de eventos" do IntentEngine)

| Provider | Fonte | Padrões |
|---|---|---|
| `WebsiteIntentProvider` | HTML do site | carreira, job, produto, expansão |
| `JobPostingIntentProvider` | Job boards | vagas com `posted_at` |

### `IntentScorer` (decay temporal)

- Decay linear: `score = confidence * max(0, 1 - days_since / decay_days)`
- Sem `observed_at` → não aplica decay (consolidação §27: não esconder UNKNOWN)
- `trigger_threshold` por oferta (via `OfferProfile.intent`)
- Retorna `triggered: bool` (≥ threshold)

### Como adicionar novo producer

1. Criar classe que implementa `IntentProvider` (name + `async collect`)
2. `IntentProviderRegistry.register(provider)`
3. Adicionar ao `build_default_intent_registry()` se for padrão
4. **Pipeline não muda** — registry é consultado pelo orchestrator

### Tests: 17 (14 unit + 3 integration). Suite total: 178.


---

## Fase F — Event Discovery (Troféus)

> **Status:** 🔵 SCAFFOLDING — executor/timing testados; provider externo não configurado.

**Contexto AlphaMec:** Principal motor de receita é venda de troféus
para eventos esportivos/corporativos sazonais. O pipeline de Event
Discovery é o **coração do funil** da EJ.

### Critério satisfeito

> "Sistema consegue transformar um evento futuro em oportunidade
> comercial rastreável."

Validado por tests:
- Copa Paulista de Karate em 30 dias → organizador resolvido + timing 80+ + match trophies
- 5 eventos (3 duplicados) → 4 únicos ranqueados por urgência

### Componentes

| Componente | Responsabilidade |
|---|---|
| `EventOpportunity` | Entidade com event_date/expires_at/registration_status |
| `EventDiscoveryProvider` (Protocol) | Contract: name + `async discover()` |
| `EventDiscoveryRegistry` | Mapa de providers |
| `EventDiscoveryExecutor` | Pipeline: provider → organizer → timing → match |
| `OrganizerResolver` | Resolve nome → federação (cadastro + fuzzy) |
| `EventTimingScorer` | Urgência 0-100 (sweet spot 7-60 dias) |
| `SportsFederationProvider` | Adapter para federações (stub testável) |

### Timing Score

| Dias até evento | Urgência | Score |
|---|---|---|
| 0 (hoje) | today | 100 |
| 1-6 | high | 90 |
| 7-30 | high | 100 |
| 31-60 | medium | 100 |
| 61-180 | low | 40-80 |
| 180+ | very_low | 10-40 |
| passado | expired | 0 |

### Bugfixes reais encontrados durante TDD

1. `EventOpportunity` era `frozen=True` → quebrava deepcopy em tests
2. `asdict()` não funciona com nested `mappingproxy` (organizer/timing)
3. Executor não executava providers quando plan era vazio
4. `EventTimingScorer` decaimento pouco agressivo para eventos > 180 dias

### Tests: 21 (19 unit + 2 integration cenários AlphaMec). O número é histórico;
o status operacional está na matriz de auditoria ao final deste documento.


---

## Fase G — Decision Maker Resolution Real

> **Status:** 🟠 PARTIAL — chamado pelo enrichment e persistido em JSONB; falta persistência própria.

**Critério satisfeito:** "Pipeline retorna pessoa(s) reais ou um estado
explícito de falha, não apenas roles desejados."

### Componentes

| Componente | Função |
|---|---|
| `PersonContact` | Pessoa real (não role) com source_merged |
| `ResolutionResult` | Status: resolved / partial / not_found |
| `DecisionMakerResolver` | Converte fontes em pessoas (nunca inventa) |
| `IdentityResolver` | Dedup por CPF → email+nome |
| `ContactConfidence` | Agrega confidence de múltiplas fontes (max + boost) |
| `ContactVerification` | Verifica email MX + identidade; heurística nunca verificada |

### Status possíveis

| Status | Significado |
|---|---|
| `resolved` | Tem pessoa + pelo menos 1 com CPF |
| `partial` | Tem pessoas mas sem CPF (heurística) |
| `not_found` | **Falha explícita** — fonte vazia ou sem retorno |
| `failed` | Erro irrecuperável |

### Regra de ouro: NÃO INVENTA PESSOAS

Se `sources` é vazio ou todas retornam listas vazias, `ResolutionResult`
retorna `not_found` com `people=[]` e `audit.reason` explicativo.

### Verification

- `email_verified`: True só se MX válido + fonte != heuristic
- `identity_verified`: True se tem CPF
- Heurística de email (sem CPF): **nunca verificada** (gate de outreach)
- Status final: `fully_verified` / `identity_verified_no_email` / `email_verified_no_identity` / `partial` / `no_email`

### Tests: 15 (13 unit + 2 integration cenários end-to-end). Os testes não
substituem a validação com providers e PostgreSQL reais.


### Auditoria profunda (pós-PR7)

Bugs reais achados na revisão:
1. **DecisionMakerResolver não era chamado por ninguém** — isolado.
   → Plugado em `ContactEnrichmentService.enrich_contacts()` (linha 602+).
2. **ContactVerification dependia de `mock_mx_check` injetado** — quebrava produção.
   → Agora tenta `EmailVerificationService` real; fallback `pending_real_check`.
3. **IdentityResolver não normalizava acentos** — Conceição ≠ Conceicao.
   → Validado: CPF já normaliza, email+nome é case-insensitive.
4. **`_status` não tinha `pending_real_check`** — adiciona distinção clara.

---

## Fase H — Learning & Metrics

> **Status:** 🔵 SCAFFOLDING — métricas testadas em memória; falta persistência/API/BI.

**Critério satisfeito:** "É possível provar se uma alteração AUMENTOU
ou REDUZIU a qualidade comercial."

### Componentes

| Componente | Função |
|---|---|
| `OutcomesRegistry` | Persiste outcomes comerciais (WON/LOST/...) com org_id/offer_key/version |
| `CommercialMetrics` | Conversion rate, ticket médio, métricas por provider, time-to-conversion |
| `VersionComparator` | A/B testing: v1 vs v2 com threshold de regressão (-5pp default) |

### `VersionComparator` — A/B testing

```python
result = comparator.compare("trophies", "1.0", "2.0")
# {
#   "v1_conversion": 16.7, "v2_conversion": 40.0,
#   "delta": 23.3, "is_regression": False, "is_improvement": True
# }
```

- `min_samples=10` (default) — sem samples suficientes: `is_conclusive=False`
- `regression_threshold=-5.0` (default) — queda de 5pp = regressão
- Comparação por offer_key + offer_version

### Cenário AlphaMec (validado por test)

1. 30 leads v1.0 → 5 WON (16.7%) — prompt original
2. 30 leads v2.0 → 12 WON (40%) — prompt melhorado
3. `VersionComparator` detecta `is_improvement=True`, delta=+23.3pp
4. Métricas por provider: `google_places` 17/60 WON (28.3%)
5. Ticket médio: R$ 1900 (mistura v1 R$1500 + v2 R$2000)

### Tests: 15 (14 unit + 1 integration AlphaMec). Os testes comprovam contratos em memória; não substituem PostgreSQL/BI.

---

## Auditoria final (2026-09-04)

Os status anteriores foram revisados contra callers, migrations, providers e
testes. O mapa `docs/00-status-mapa.md` é a fonte operacional. O grafo mostrou
caller de produção para `OfferMatcher` no `enrichment_orchestrator`, mas não
para `EventDiscoveryExecutor`, `IntentProviderRegistry` ou `LearningMetrics`.
O E2E de outreach permanece condicionado a `E2E_DATABASE_URL`; a migration
`e8f9a0b1c2d3` de notificações está aplicada no banco local.

