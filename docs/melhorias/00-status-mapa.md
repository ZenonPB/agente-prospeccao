# Mapa de status — pacote de melhorias (`docs/melhorias/`)

> **Snapshot: 2026-09-04**, branch `feat/fase2-sinais-e-episteme`.
> Este arquivo é a fonte única para entender **o que está feito, o que está
> parcial e o que falta** em cada documento de `docs/melhorias/`.
>
> O **plano macro** (`docs/00-plano-melhorias-prospeccao.md`) define 47 documentos
> em 3 capítulos (Descoberta/qualidade · Arquitetura universal · Decisores/contatos).
> Os arquivos do diretório usam o sufixo **`-FEITO.md`** quando a entrega está
> concluída; os demais continuam com o nome original até serem marcados.

## Legenda

| Marca | Significado |
|---|---|
| ✅ **FEITO** | Implementação completa e validada (arquivo `-FEITO.md`). |
| 🟡 **PROPOSTO** | Documento de design ainda não implementado. |
| 🟠 **PARCIAL** | Há fundação/recurso relacionado no código; o doc descreve evolução. |

## Capítulo 1 — Descoberta, pré-ranking e qualidade

| # | Doc | Status | Resumo do estado |
|---|---|---|---|
| 01 | `01-candidate-pre-scoring-FEITO.md` | ✅ | Pre-scoring determinístico sem LLM (`candidate_pre_scoring_service`), gate com threshold/top_k no pipeline e descartes auditados em `prescoring_discards`. |
| 02 | `02-opportunity-score-vector-FEITO.md` | ✅ | `score_vector` (need/commercial_fit/digital_maturity/contactability) com `overall` agregado por perfil e `formula_version` fixada no backend. |
| 03 | `03-template-landing-pages-FEITO.md` | ✅ | Seed dedicado "Landing Pages" com prescoring/enrichment/playbook próprios. |
| 04 | `04-places-multi-query-FEITO.md` | ✅ | `campaigns.search_queries` + `discovery_multi_query` (limite proporcional, dedup por place_id, `source_queries`). |
| 05 | `05-search-query-generation-FEITO.md` | ✅ | `generate_queries(service, segment, city, ...)`: LLM expander com fallback determinístico + dedup. |
| 06 | `06-candidate-vs-lead-FEITO.md` | ✅ | Candidate como estado lógico no pipeline; descarte persistido em `prescoring_discards` (idempotente). Tabela física fica para quando métricas de retrieval exigirem. |
| 07 | `07-budgeted-enrichment-FEITO.md` | ✅ | Candidatos abaixo do threshold não viram Lead nem consomem CNPJ/site/LLM/contato. |
| 08 | `08-enrichment-order-by-service-FEITO.md` | ✅ | Ordem + skip + stop_after declarados em `enrichment_strategy`; planner `plan_enrichment_run` auditável. |
| 09 | `09-rating-count-by-vertical-FEITO.md` | ✅ | `interpret_rating_count(profile_key, raw_count, segment)`: buckets por vertical (fraco/médio/bom/muito_bom/ótimo) com score 0-100. |
| 10 | `10-niche-prior-learning-FEITO.md` | ✅ | `compute_niche_prior(org_id, service, segment)`: prior score por outcomes. |
| 11 | `11-learning-from-sales-outcomes-FEITO.md` | ✅ | `record_outcome()` + `summarize_learning()`: agregação por sinal/faixa/canal. |
| 12 | `12-precision-at-k-FEITO.md` | ✅ | `precision_at_k(ranked_leads, k)`: fração top-K que convertiram. |
| 13 | `13-chain-detection-FEITO.md` | ✅ | `detect_chain(lead_data)`: classificação INDEPENDENT/SMALL_CHAIN/FRANCHISE/ENTERPRISE/UNKNOWN com evidência + confiança. |
| 14 | `14-decision-maker-accessibility-FEITO.md` | ✅ | Dimensão `decision_maker_accessibility` adicionada ao VECTOR_WEIGHTS (peso 0, ativável). |
| 15 | `15-golden-lead-patterns-FEITO.md` | 🟡 | Não há matcher de padrões compostos (ex.: `landing_local_golden_v1`) — o seed Landing Pages aproxima por pesos, mas sem padrão explícito com explicação por evidência. |
| 16 | `16-why-prospect-card-FEITO.md` | ✅ | Card do lead expõe `why_signals` (top 3 títulos de evidence). |


## Capítulo 2 — Arquitetura universal e inteligência por vertical

| # | Doc | Status | Resumo do estado |
|---|---|---|---|
| 17 | `17-prospecting-profile-FEITO.md` | ✅ | `resolve_prospecting_profile` centralizado (deriva de `enrichment_steps` + override em `prescoring_config.profile`). Entidade **versionável** com discovery/decision-maker/outreach strategy segue nos docs 22/25. |
| 18 | `18-universal-prospecting-questions-FEITO.md` | ✅ | `build_universal_questions(profile_key)`: 6 perguntas formais (icp/need/buying_power/timing/decision_maker/outreach) + validação de cobertura. |
| 19 | `19-icp-vs-intent-FEITO.md` | ✅ | `icp_vs_intent()` (BuyingTrigger service) distingue ICP fixo de intent temporal com classificação TIMELY/PROFILED/COLD. |
| 20 | `20-signal-registry-FEITO.md` | ✅ | Registry universal com chaves canônicas, metadados, `make_signal` com regras epistêmicas e `merge_signals` com dedup semântico. |
| 21 | `21-enrichment-capability-registry-FEITO.md` | ✅ | Capabilities com custo/requires/produces + planner `plan_enrichment_run` (skip/stop_after auditáveis). |
| 22 | `22-discovery-planner-FEITO.md` | ✅ | `DiscoveryPlanner.plan()` (seam profundo ProspectingProfile→providers/queries/budget, auditável). |
| 23 | `23-cnae-as-discovery-provider.md` | 🟠 | `cnae_discovery_service.py` existe e está integrado (BrasilAPI + Minha Receita + CNPJá); basta ser plugado como provider nativo de um futuro Discovery Planner. |
| 24 | `24-intent-engine-FEITO.md` | ✅ | `IntentEngine.detect_events()` + `score_and_trigger()` (intent_score/buying_trigger/why_now) sobre sinais. |
| 25 | `25-decision-maker-strategy-by-vertical-FEITO.md` | ✅ | `resolve_contact_strategy(profile_key)`: mapa profile→ordered providers + channel priority. |
| 26 | `26-buying-trigger-FEITO.md` | ✅ | `detect_buying_triggers()` converte intent events → triggers acionáveis com confidência. |
| 27 | `27-opportunity-vector-v2-FEITO.md` | ✅ | VECTOR_WEIGHTS expandido (`icp_fit/intent/buying_power/reachability/timing` peso 0, compatível) + formula_version v2. |
| 28 | `28-prospecting-hypothesis-FEITO.md` | ✅ | `build_hypothesis(profile_key)`: problem/hypothesis/expected_lift + key_signals. |
| 29 | `29-epistemic-status-FEITO.md` | ✅ | `EpistemicStatus` aplicado na fábrica de sinais (FACT sem fonte rebaixado a INFERENCE; UNKNOWN sem valor; HYPOTHESIS com `evidence_refs`); prompt de scoring distingue fato/inferência/hipótese. |
| 30 | `30-discovery-questions-FEITO.md` | ✅ | `discovery_questions_for(profile_key)`: perguntas de qualificação por vertical. |
| 31 | `31-vertical-pack-FEITO.md` | ✅ | `vertical_pack_for(profile_key)`: enrichment_pack declarativo por perfil. |
| 32 | `32-archetypes-as-fallback.md` | 🟡 | `TemplateGenerationService` + `template_router` cobrem o fallback LLM/exact/fuzzy → Genérico, mas não há **archetype** explícito como bootstrap de um pack novo. |
| 33 | `33-three-level-learning-FEITO.md` | ✅ | `ThreeLevelLearning.resolve(key, vertical, org)`: precedência GLOBAL→VERTICAL→ORGANIZATION. |


## Capítulo 3 — Decisores e contatos

| # | Doc | Status | Resumo do estado |
|---|---|---|---|
| 34 | `34-decision-maker-resolution-pipeline.md` | 🟠 | Pipeline existe **por partes**: (a) TargetRole via `playbook.linkedin_queries`/`ContactRole`; (b) PeopleDiscovery multi-provider (Receita/QSA, Hunter domain-search, busca site, LinkedIn assistido); (c) `linkedin_match_status` faz verificação semântica. Falta **orquestrador único** `TargetRoleResolver → PeopleDiscovery → IdentityResolution → ContactDiscovery → Verification → DecisionMakerScore`. |
| 35 | `35-people-discovery-service.md` | 🟠 | `ContactEnrichmentService` é o equivalente funcional (Hunter + Receita/QSA + heurística determinística + LinkedIn assistido), mas **não há interface `PeopleDiscoveryService`** plugável com providers intercambiáveis. |
| 36 | `36-qsa-decision-makers.md` | 🟠 | `cnpj_service._parse_brasilapi` lê `qsa[]` e gera contatos com `role`/`role_label`; sócios entram como decisores econômicos. Falta classificá-los explicitamente como `LEGAL_DECISION_MAKER`/`ECONOMIC_BUYER` e permitir que a vertical priorize gerente técnico em vez deles. |
| 37 | `37-person-database-provider.md` | 🟡 | Hunter é o único provider de base de pessoas hoje (domain-search). Não há camada de abstração que permita trocar/encapsular provedores de pessoas (Apollo, Snov.io, etc.) com quota. |
| 38 | `38-email-finder-after-identity.md` | 🟠 | Hoje o `ContactEnrichmentService` faz Hunter domain-search quando não há nome (doc 35), mas **email-finder por nome+domínio não é separado como fase posterior**; os dois caminhos rodam juntos quando Hunter key existe. |
| 39 | `39-email-pattern-inference.md` | 🟡 | Heurística determinística já infere `firstname.lastname@dominio` no fallback, mas **não há persistência de padrão por domínio com `source=pattern_inference`/`confidence`/`verification_status`**. |
| 40 | `40-contact-confidence-score.md` | 🟠 | `Contact.confidence` (0–100) + `linkedin_confidence` + `linkedin_match_status` já existem e a UI exibe badge (≥50 verde). Falta **separar `decision_maker_fit` × `identity_confidence` × `contact_confidence`** como três scores independentes. |
| 41 | `41-channel-priority-by-vertical-FEITO.md` | ✅ | `CHANNEL_PRIORITY_BY_PROFILE` em decision_maker_strategy_service. |
| 42 | `42-routable-contact.md` | 🟡 | Não há modelagem `DIRECT_CONTACT` vs `ROUTABLE_CONTACT` (PABX + target_person). `Lead.phone`/`Contact.phone` são telefones crus. |
| 43 | `43-multiple-buyers.md` | 🟠 | `Lead` aceita múltiplos `Contact`s, e `ContactRole` classifica o cargo — porém **não há `buyer_role` (ECONOMIC_BUYER/TECHNICAL_BUYER/CHAMPION/INFLUENCER/GATEKEEPER)** separado do cargo factual, nem UI de comitê de compra. |
| 44 | `44-cascade-contact-search.md` | 🟡 | Hoje o `ContactEnrichmentService` segue uma ordem fixa (Receita → Hunter → heurística → LinkedIn assistido). **Não há cascata explícita com early stopping** baseado em `identity_confidence`/`actionable` e por vertical. |
| 45 | `45-company-identity-resolver-FEITO.md` | ✅ | `CompanyPersonService.get_or_create_company()` por CNPJ/domínio/nome. |
| 46 | `46-domain-first-person-search.md` | 🟡 | `linkedin_assist_service` e a busca Hunter já usam domínio quando disponível, mas não há um orquestrador explícito `domain + titles` com fallback para `name + location`. |
## Resumo executivo do pacote

- **Total:** 47 documentos · **✅ FEITO: 33** · **🟠 PARCIAL: 9** · **🟡 PROPOSTO: 9**
- **Cobertura por capítulo:**
  - Descoberta/qualidade: 17 ✅, 2 🟠, 0 🟡 (de 17)
  - Arquitetura universal: 13 ✅, 1 🟠, 3 🟡 (de 17)
  - Decisores/contatos: 1 🟠, 12 🟡 (de 13)

## Como ler este pacote na prática

- Se a linha diz **🟠 PARCIAL**, há fundação utilizável: o trabalho é
  **estender**, não criar do zero (modelo/tabela/serviço já existem).
- Se a linha diz **🟡 PROPOSTO**, o doc inteiro é a spec: o trabalho é
  **implementar do zero** respeitando contratos que já existem.
## Próxima fase (Fase 3 do plano de melhorias — candidatos naturais)

Ordenados por prioridade (P0 primeiro) e respeitando as dependências:

1. **#18** Seis perguntas universais do agente (P1) — sem contrato de raciocínio
   entre as camadas; veda a criação de um agente "genuíno".
2. **#22 Discovery Planner** (P0) + **#23 CNAE provider** (P0, já parcial) — destrava
   o suporte nativo a Engenharia/ERP sem passar por Places.
3. **#19 Separar ICP Fit de Intent** (P0) — destrava o **Intent Engine (#24)**.
4. **#24 Intent Engine** (P0) — eventos recentes viram sinais temporais com
   decay, alimentando `intent_score` (vetor universal).
5. **#27 Opportunity vector v2** (P0) — completar o vetor (`icp_fit`,
   `intent`, `buying_power`, `reachability`, `timing`) e UI por dimensão.
6. **#25 Decision-maker strategy por vertical** (P0) — `decision_maker_roles`
   + `buyer_role` no `ProspectingProfile`; entrada do **#34 Decision-maker
   pipeline**.
7. **#31 Vertical Pack** (P0) — empacotar toda a inteligência em entidade
   declarativa versionável; prepara a fundação para **#33 three-level
   learning** e **#32 archetypes as fallback**.
8. **#34 Decision Maker Resolution Pipeline** (P0) + **#35 PeopleDiscovery**
   (P0) + **#36 QSA** (P0, parcial) — unificar o caminho
   `empresa → cargo-alvo → pessoa → canais → verificação` em um pipeline
   auditável com cascata explícita (#44) e confiança de contato (#40).
## Pendências de housekeeping

- O arquivo **`docs/melhorias/00-plano-melhorias-prospeccao.md`** e seu espelho
  **`docs/00-plano-melhorias-prospeccao.md`** (na raiz de `docs/`) precisam ter
  o sufixo `✅ FEITO` realocado em todos os itens quando os docs forem
  entregues — hoje eles só marcam os 12 que já estão `-FEITO.md`. Conforme
  este mapa for atualizado, o plano macro precisa refletir (não basta o
  nome do arquivo).
- Nenhum arquivo `-FEITO.md` precisa ser renomeado: o sufixo já está
  consistente em todos os 12 docs entregues.


Itens secundários depois do P0: #14 accessibility (parcial), #38 email finder
after identity (parcial), #39 pattern inference, #41 channel priority, #42
routable contact, #43 multiple buyers (parcial), #45 company identity resolver
(parcial), #46 domain-first person search, #47 actionable contact rate.

Itens de BI/learning para fechar o ciclo: #11 outcomes, #12 precision@K, #10
niche priors, #33 three-level learning, #28 prospecting hypothesis, #26 buying
trigger, #15 golden lead patterns, #13 chain detection, #30 discovery
questions, #09 rating buckets por vertical, #05 search query generation.


- Os 🟡 P0 do plano macro são o caminho natural para a **próxima fase de
  evolução** após a Fase 2 (sinais/enrichment): ver seção _Próxima fase_.


| 47 | `47-actionable-contact-rate.md` | 🟡 | Métrica não existe em `/analytics`. Hoje há `Contact.confidence` ≥ 50 e `email_verified`, mas **não há taxa consolidada** que distinga direct/routable/institutional. |

