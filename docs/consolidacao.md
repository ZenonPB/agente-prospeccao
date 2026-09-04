# Plano de Consolidação e Evolução --- Agente de Prospecção

> **Repositório:** `ZenonPB/agente-prospeccao`\
> **Objetivo deste documento:** transformar as fundações arquiteturais
> já criadas em capacidades realmente operacionais, corrigir
> inconsistências entre documentação e implementação e preparar o
> sistema para prospecção orientada por oferta, múltiplas verticais,
> intenção temporal, descoberta de eventos e resolução real de
> decisores.
>
> **Regra de execução:** este documento deve ser tratado como um plano
> de engenharia. Um item só pode ser marcado como **FEITO** quando
> estiver integrado ao fluxo real, possuir comportamento verificável e
> testes que provem o contrato descrito. Criar apenas uma interface,
> helper, enum, registry, retorno estático ou placeholder **não**
> caracteriza conclusão.

------------------------------------------------------------------------

## 1. Diagnóstico executivo

O projeto evoluiu de uma prospecção fortemente acoplada a Landing
Pages/Google Places para uma arquitetura muito mais genérica, com
conceitos importantes como:

-   pré-scoring determinístico;
-   Signal Registry;
-   status epistêmico;
-   Prospecting Profile;
-   enrichment por capabilities;
-   Discovery Planner;
-   CNAE como fonte de descoberta;
-   ICP separado de Intent;
-   Intent Engine;
-   Buying Trigger;
-   Opportunity Vector;
-   estratégias de decisor por vertical;
-   Contact Provider Registry;
-   resolução de empresa/pessoa;
-   métricas de aprendizado.

A direção arquitetural está correta. O problema atual não é falta de
abstrações: é a distância entre **contrato arquitetural** e **capacidade
operacional**.

Há componentes documentados como concluídos que, na prática, ainda são:

1.  interfaces;
2.  seams arquiteturais;
3.  helpers;
4.  mappings hardcoded;
5.  retornos estáticos;
6.  placeholders aguardando provider;
7.  funções que descrevem uma cascata, mas não executam a cascata
    completa.

Portanto, a próxima fase não deve adicionar dezenas de novas abstrações
independentes. Deve consolidar o que existe em um fluxo executável,
orientado por oferta e mensurável.

------------------------------------------------------------------------

# 2. Primeiro problema: documentação de status não representa a realidade

## 2.1 Problema

`docs/melhorias/00-status-mapa.md` declara todos os 47 documentos como
concluídos, mas o próprio repositório ainda contém documentos propostos
e implementações parciais.

Existem ainda trechos no mapa que tratam Vertical Pack, Decision Maker
Pipeline e outros recursos como próximos passos, ao mesmo tempo em que o
resumo executivo afirma `47 FEITO`.

Isso é perigoso porque:

-   desenvolvedores passam a considerar contratos incompletos como
    produção;
-   agentes de IA recebem uma visão falsa do estado do projeto;
-   futuras alterações podem ser construídas sobre premissas
    inexistentes;
-   bugs arquiteturais ficam mascarados por documentação otimista.

## 2.2 Nova classificação obrigatória

Adotar quatro estados:

``` text
✅ COMPLETE
🟠 PARTIAL
🔵 SCAFFOLDING
🟡 PROPOSED
```

### COMPLETE

Só quando:

-   código existe;
-   está conectado ao pipeline real;
-   não depende de retorno fake/placeholder para cumprir seu objetivo;
-   possui testes relevantes;
-   documentação corresponde ao comportamento;
-   há observabilidade mínima.

### PARTIAL

Existe comportamento real, mas faltam partes relevantes.

### SCAFFOLDING

Existe contrato/interface/helper, mas a capacidade ainda não acontece de
ponta a ponta.

### PROPOSED

Existe apenas especificação.

## 2.3 Arquivos a revisar

Obrigatoriamente:

``` text
docs/melhorias/00-status-mapa.md
docs/melhorias/00-plano-melhorias-prospeccao.md
docs/00-plano-melhorias-prospeccao.md
docs/architecture.md
docs/context.md
```

Também revisar cada `*-FEITO.md`.

O sufixo `-FEITO.md` não deve ser usado como fonte da verdade. Se a
implementação não satisfizer os critérios acima, renomear ou alterar
explicitamente o status interno.

## 2.4 Critério de aceite

Criar uma tabela por capability:

``` text
Capability
Status
Entry point
Pipeline integration
Persistence
Provider real?
Tests
Known limitations
```

O mapa deve poder responder: **"onde esta capacidade realmente roda?"**

------------------------------------------------------------------------

# 3. Separar Archetype, Prospecting Profile e Offer Profile

## 3.1 Problema atual

`prospecting_profile_service.py` trabalha principalmente com:

``` text
web_presence
business_opportunity
industrial
```

Esses perfis são úteis como arquétipos, mas genéricos demais para
representar ofertas comerciais.

`industrial`, por exemplo, não é suficiente para distinguir:

-   projeto mecânico;
-   desenho técnico;
-   manual de máquinas;
-   NR-12;
-   impressão 3D;
-   corte/gravação a laser.

As empresas ideais, sinais, decisores, gatilhos e canais podem ser
completamente diferentes.

## 3.2 Modelo desejado

Criar três níveis conceituais:

``` text
Archetype
    ↓
Vertical
    ↓
OfferProfile
```

Exemplo:

``` text
industrial
└── mechanical_engineering
    ├── mechanical_project
    ├── technical_drawing
    ├── machine_manual
    └── nr12_documentation

custom_products
└── awards
    └── trophies

digital
└── web_presence
    └── landing_page
```

### Archetype

Fallback genérico.

### Vertical

Contexto de mercado.

### OfferProfile

Unidade principal de inteligência comercial.

## 3.3 Novo contrato de OfferProfile

Criar entidade declarativa versionada contendo, no mínimo:

``` yaml
key:
version:
archetype:
vertical:
offer:

icp:
  company_sizes:
  segments:
  cnaes:
  exclusions:
  geography:

discovery:
  providers:
  target_candidates:
  provider_budgets:
  query_strategy:

prescoring:
  required_signals:
  weights:
  threshold:
  top_k:
  on_insufficient_data:

enrichment:
  steps:
  stop_conditions:
  max_cost:

signals:
  positive:
  negative:
  disqualifiers:

intent:
  event_weights:
  decay:
  trigger_threshold:

decision_makers:
  roles:
  buyer_types:
  priority:

channels:
  priority:

qualification:
  questions:

outreach:
  angle:
  evidence_requirements:
```

## 3.4 Arquivos

Refatorar:

``` text
services/workers/src/services/prospecting_profile_service.py
services/workers/src/services/archetype_service.py
services/workers/src/services/vertical_pack_service.py
services/workers/src/seeds/scoring_templates.py
```

Se `vertical_pack_service.py` ainda não existir de forma funcional,
criá-lo.

Sugestão:

``` text
services/workers/src/prospecting/
    archetypes.py
    offer_profiles.py
    profile_resolver.py
    schemas.py
```

Evitar continuar aumentando um único `prospecting_profile_service.py`.

## 3.5 Compatibilidade

Campanhas antigas devem continuar funcionando.

Resolver:

``` text
explicit offer_profile
    ↓ fallback
vertical
    ↓ fallback
archetype
    ↓ fallback
generic
```

Nunca quebrar campanhas existentes silenciosamente.

------------------------------------------------------------------------

# 4. Transformar Vertical Pack em configuração realmente central

## Problema

Atualmente muita inteligência continua distribuída em constantes e
mappings Python.

Exemplos conceituais:

-   pesos por profile;
-   ICP por profile;
-   roles por profile;
-   channel priority;
-   trigger maps;
-   rating buckets.

Isso gera várias fontes da verdade.

## Mudança

O Vertical/Offer Pack deve se tornar a fonte declarativa da inteligência
comercial.

Engines devem consumir configuração, não conhecer ofertas específicas.

### Errado

``` python
if profile_key == "industrial":
    ...
```

### Desejado

``` python
profile.discovery.providers
profile.intent.event_weights
profile.decision_makers.roles
```

## Arquivos a refatorar

``` text
prospecting_profile_service.py
buying_trigger_service.py
intent_engine_service.py
decision_maker_strategy_service.py
decision_maker_pipeline_service.py
candidate_pre_scoring_service.py
opportunity_score/vector service
```

## Regra

O core não deve precisar ser alterado para cadastrar uma nova oferta
comum.

------------------------------------------------------------------------

# 5. Criar OfferMatcher

## 5.1 Objetivo

Hoje a lógica tende a partir de:

``` text
serviço escolhido
→ procurar empresas
```

Adicionar também:

``` text
empresa descoberta
→ sinais
→ ofertas compatíveis
```

Uma empresa pode ter oportunidades diferentes simultaneamente.

## 5.2 Resultado esperado

``` json
{
  "company_id": "...",
  "matches": [
    {
      "offer_profile": "technical_drawing",
      "score": 92,
      "evidence_refs": [],
      "why": []
    },
    {
      "offer_profile": "mechanical_project",
      "score": 78
    }
  ]
}
```

## 5.3 Novo serviço

Criar:

``` text
services/workers/src/services/offer_matcher_service.py
```

Responsabilidades:

-   receber sinais normalizados;
-   carregar OfferProfiles elegíveis;
-   calcular fit por oferta;
-   respeitar disqualifiers;
-   produzir evidências;
-   não confundir ICP com Intent;
-   retornar top-N oportunidades.

## 5.4 Persistência

Se fizer sentido no modelo existente, criar conceito de:

``` text
LeadOpportunity
```

com:

``` text
lead_id
offer_profile_key
offer_profile_version
icp_score
intent_score
opportunity_score
status
evidence
created_at
updated_at
```

Não sobrescrever o score global do Lead para representar múltiplas
ofertas.

## 5.5 Testes

Testar explicitamente uma mesma empresa sendo:

-   excelente para desenho técnico;
-   razoável para projeto mecânico;
-   ruim para landing page.

------------------------------------------------------------------------

# 6. Refazer Discovery Planner como planner real

## 6.1 Problema atual

`discovery_planner_service.py` ainda possui decisões simplificadas e
budgets estáticos.

O planner deveria decidir **como encontrar candidatos para aquela
oferta**, e não apenas retornar Places/CNAE com valores genéricos.

## 6.2 Novo contrato

Entrada:

``` text
OfferProfile
Campaign
Organization
Budget
Geography
Historical learning
```

Saída:

``` json
{
  "plan_id": "...",
  "profile_version": "...",
  "target_candidates": 300,
  "providers": [
    {
      "provider": "cnae",
      "priority": 1,
      "budget": 150,
      "queries": [],
      "filters": {},
      "expected_signal_types": [],
      "stop_conditions": []
    }
  ]
}
```

## 6.3 Planner não pode só descrever

O pipeline deve consumir o plano.

Fluxo obrigatório:

``` text
Campaign
→ OfferProfileResolver
→ DiscoveryPlanner
→ DiscoveryPlan
→ Provider Executor
→ Candidate Normalizer
→ Dedup
→ PreScoring
```

## 6.4 Arquivos

Modificar:

``` text
services/workers/src/services/discovery_planner_service.py
services/api/src/pipeline_worker.py
services/workers/src/services/places_service.py
services/workers/src/services/cnae_discovery_service.py
```

Criar, se necessário:

``` text
services/workers/src/services/discovery_provider_registry.py
services/workers/src/services/discovery_executor_service.py
```

## 6.5 Provider contract

``` python
discover(plan_step, context) -> DiscoveryResult
```

Todos os providers devem produzir candidatos normalizados e provenance.

------------------------------------------------------------------------

# 7. Melhorar CNAE Discovery

## Problema

`cnae_discovery_plan()` aceita CNAE, mas falta a inteligência:

``` text
oferta → CNAEs adequados
```

## Mudança

O OfferProfile deve declarar:

``` yaml
discovery:
  cnae:
    primary:
    secondary:
    exclusions:
```

Criar resolver semântico apenas como fallback.

## Arquivos

``` text
cnae_discovery_service.py
discovery_planner_service.py
offer_profiles.*
```

## Requisitos

Cada candidato vindo de CNAE deve registrar:

``` text
source
cnae_match
matched_rule
query/filter
retrieved_at
```

------------------------------------------------------------------------

# 8. Corrigir Candidate Pre-Scoring

## O que manter

O desenho atual é bom:

-   determinístico;
-   barato;
-   antes de enrichment pesado;
-   auditável;
-   `INSUFFICIENT_DATA`;
-   threshold/top-k.

## Melhorias

### 8.1 Não usar presença de sinal como verdade suficiente

Garantir que `required_signals` diferencie:

``` text
not_observed
observed_false
observed_true
unknown
```

### 8.2 Usar interpretação contextual de rating_count

Atualmente há `interpret_rating_count()`, mas o pre-score precisa
realmente consumir a interpretação configurada, em vez de manter apenas
uma normalização fixa `min(count, 50)`.

### 8.3 Pesos por OfferProfile

Remover dependência futura de defaults genéricos.

### 8.4 Persistir versão

Todo descarte deve guardar:

``` text
offer_profile_key
offer_profile_version
formula_version
```

Assim um lead descartado pode ser reavaliado quando a regra mudar.

## Arquivos

``` text
candidate_pre_scoring_service.py
prospecting_profile_service.py
signal_registry.py
model/migration de prescoring_discards
```

------------------------------------------------------------------------

# 9. Separar Intent Collection de Intent Interpretation

## 9.1 Problema

O Intent Engine interpreta sinais como `HIRING`, `NEW_BRANCH`, etc., mas
não é responsável por descobrir a maioria desses eventos.

Criar separação explícita:

``` text
Intent Providers
    ↓
FACT signals
    ↓
Intent Engine
    ↓
Intent Events
    ↓
Buying Triggers
```

## 9.2 Novos providers

Começar com poucos, mas reais:

``` text
WebsiteIntentProvider
JobPostingIntentProvider
EventDiscoveryProvider
```

Depois:

``` text
CompanyNewsProvider
SocialIntentProvider
ProcurementIntentProvider
```

## 9.3 Contract

``` python
collect(company, offer_profile, context) -> list[Signal]
```

Provider produz fatos. Engine produz inferências.

Nunca deixar provider criar `FACT` sem source/evidence.

------------------------------------------------------------------------

# 10. Refazer Intent Score

## Problema

Média de confidence não representa quantidade, relevância, temporalidade
ou vertical.

## Fórmula desejada

Cada evento:

``` text
contribution =
event_weight_for_offer
× confidence
× recency_decay
× source_reliability
```

Combinar com saturação para evitar score artificialmente infinito.

Uma opção:

``` text
score = 100 × (1 - Π(1 - contribution_i))
```

com contribuições normalizadas em `[0,1]`.

## Recency

Cada evento deve possuir:

``` text
observed_at
event_at
expires_at
```

Aplicar decay configurável por tipo.

Exemplo:

``` text
NEW_BRANCH: decay lento
HIRING: médio
EVENT_REGISTRATION_OPEN: rápido
```

## Arquivos

``` text
intent_engine_service.py
buying_trigger_service.py
signal_registry.py
offer profile definitions
```

## Versionamento

Persistir:

``` text
intent_formula_version
offer_profile_version
```

------------------------------------------------------------------------

# 11. Refatorar Buying Trigger

## Problema

`ICP_BY_PROFILE` e `TRIGGER_MAP` centralizam regras específicas no
engine.

## Mudança

Mover regras para OfferProfile.

Exemplo:

``` yaml
intent:
  events:
    NEW_EQUIPMENT:
      weight: 0.95
      trigger: "Possível investimento/adequação relacionado a novo equipamento"
    HIRING_MECHANICAL_ENGINEER:
      weight: 0.85
```

`buying_trigger_service.py` deve:

-   receber evento;
-   consultar configuração;
-   gerar trigger;
-   preservar evidência;
-   nunca inventar causalidade.

### Regra epistêmica

``` text
FACT:
"empresa publicou vaga para projetista"

INFERENCE:
"empresa pode estar aumentando demanda técnica"

HYPOTHESIS:
"pode existir oportunidade para desenho técnico terceirizado"
```

Nunca converter hipótese em fato.

------------------------------------------------------------------------

# 12. Criar vertical/oferta de Troféus

## 12.1 Por que separada

Troféus não devem ser modelados apenas como "laser cutting" ou
"industrial".

A demanda é fortemente temporal:

``` text
evento
→ organizador
→ premiação
→ data
→ janela comercial
```

## 12.2 OfferProfile

Criar:

``` text
trophies
```

em vertical apropriada, como:

``` text
custom_products / awards
```

## 12.3 ICP

Possíveis organizações:

-   atléticas;
-   empresas juniores;
-   universidades;
-   escolas;
-   academias;
-   organizadores esportivos;
-   ligas;
-   associações;
-   empresas com eventos internos;
-   organizadores de hackathons;
-   feiras e competições.

## 12.4 Sinais

Adicionar ao Signal Registry conforme necessário:

``` text
EVENT_ANNOUNCED
EVENT_DATE_FOUND
EVENT_TYPE
COMPETITION_DETECTED
AWARDS_MENTIONED
AWARD_CATEGORIES_FOUND
REGISTRATION_OPEN
SPONSORSHIP_OPEN
EVENT_ORGANIZER_IDENTIFIED
```

------------------------------------------------------------------------

# 13. Criar Event Discovery

## Objetivo

Descobrir oportunidades temporais em vez de somente empresas.

## Nova entidade conceitual

Criar `EventOpportunity` ou entidade equivalente.

Campos:

``` text
id
organization_id / discovered_organization
name
event_type
event_date
location
source_url
organizer
registration_status
award_signals
confidence
observed_at
expires_at
```

## Pipeline

``` text
Event provider
→ event candidate
→ organizer resolution
→ signals
→ offer matcher
→ timing score
→ decision maker
→ outreach
```

## Novo serviço

``` text
event_discovery_service.py
```

Não acoplar Event Discovery ao provider específico.

------------------------------------------------------------------------

# 14. Decision Maker Pipeline: transformar planejamento em resolução real

## Problema

O pipeline atual resolve roles/strategy, mas não necessariamente pessoas
reais.

Além disso, `decision_maker_accessibility` não pode ser `70`
simplesmente porque existem cargos-alvo.

## Pipeline desejado

``` text
OfferProfile
↓
TargetRoleResolver
↓
Company Identity
↓
People Discovery
↓
Person Identity Resolution
↓
Role Matching
↓
Contact Discovery
↓
Verification
↓
Contact Confidence
↓
Channel Ranking
↓
Top Decision Makers
```

## Output

``` json
{
  "decision_makers": [
    {
      "person_id": "...",
      "name": "...",
      "role": "...",
      "buyer_type": "ECONOMIC_BUYER",
      "role_match": 0.91,
      "identity_confidence": 0.88,
      "contacts": [],
      "routability": "DIRECT",
      "overall_confidence": 84
    }
  ]
}
```

## Arquivos

Refatorar:

``` text
decision_maker_pipeline_service.py
decision_maker_strategy_service.py
company_person_service.py
contact_enrichment_service.py
contact_provider_registry.py
```

------------------------------------------------------------------------

# 15. Corrigir Contact Provider Registry e Cascade Search

## Problemas atuais

Evitar considerar completos fluxos que retornam:

``` text
no_provider_active
queued_for_enrich_contacts
matched: []
provider_queried
```

Esses retornos são úteis como scaffolding, não como sucesso.

## Novo provider contract

Preferencialmente assíncrono:

``` python
find_people(...)
find_email(...)
verify_email(...)
find_social_profiles(...)
```

Cada provider deve retornar:

``` text
status
provider
results
cost
quota
latency
errors
```

## Cascade real

``` text
1. QSA/Receita
2. site institucional
3. provider de pessoas
4. provider de email
5. inferência de pattern
6. verificação
```

Early stopping deve usar de verdade:

``` text
min_confidence
required_contactability
max_cost
max_steps
```

## Regra

Pattern inferido nunca deve ser tratado como contato verificado.

------------------------------------------------------------------------

# 16. Corrigir Email Pattern Inference

## Problema

A inferência é útil, mas não pode ser confundida com descoberta.

Estados:

``` text
INFERRED
PENDING_VERIFICATION
VERIFIED
INVALID
UNKNOWN
```

Persistir candidato apenas com status explícito.

Não enviar outreach automático para endereço puramente inferido, salvo
política explícita futura.

## Arquivos

``` text
contact_provider_registry.py
contact_enrichment_service.py
models de Contact
```

------------------------------------------------------------------------

# 17. Domain-First Person Search real

## Objetivo

Transformar:

``` text
domain + target roles
```

em consulta efetiva a providers.

## Fluxo

``` text
domain
→ provider registry
→ people candidates
→ normalize names/roles
→ role matcher
→ dedup
→ identity resolver
```

Fallback:

``` text
company name + location
```

`matched: []` não pode representar implementação concluída.

------------------------------------------------------------------------

# 18. Opportunity Vector v2 deve operar por oferta

O vetor deve representar uma oportunidade específica:

``` text
Lead × OfferProfile
```

e não apenas empresa global.

Dimensões recomendadas:

``` text
icp_fit
need
intent
buying_power
digital_maturity
decision_maker_accessibility
reachability
timing
commercial_fit
```

Nem toda oferta precisa usar todas.

Pesos vêm do OfferProfile.

Persistir:

``` text
vector
overall
formula_version
offer_profile_version
evidence_refs
```

------------------------------------------------------------------------

# 19. Golden Lead Patterns

Implementar de verdade padrões compostos.

Exemplo Landing Page:

``` text
NO_OWN_WEBSITE
+ HAS_INSTAGRAM
+ HAS_PHONE
+ GOOD_REPUTATION
```

Exemplo Projeto Mecânico:

``` text
TARGET_CNAE
+ INDUSTRIAL_COMPANY
+ EXPANSION_SIGNAL
+ DECISION_MAKER_REACHABLE
```

Exemplo Troféus:

``` text
EVENT_ANNOUNCED
+ COMPETITION
+ EVENT_DATE_WITHIN_WINDOW
+ ORGANIZER_IDENTIFIED
```

Patterns devem ser declarativos, versionados e explicáveis.

Criar:

``` text
golden_lead_pattern_service.py
```

se ainda não houver implementação real equivalente.

------------------------------------------------------------------------

# 20. Learning: parar de apenas calcular métricas e fechar o ciclo

## Três níveis

``` text
GLOBAL
VERTICAL/OFFER
ORGANIZATION
```

## Outcomes mínimos

``` text
contacted
replied
positive_reply
meeting_booked
proposal_sent
won
lost
not_fit
wrong_contact
```

## Learning deve responder

-   quais sinais correlacionam com resposta?
-   quais signals correlacionam com reunião?
-   quais providers geram melhores leads?
-   quais CNAEs convertem?
-   quais triggers funcionam por oferta?
-   quais cargos respondem?
-   quais canais funcionam?
-   qual custo por lead útil?

## Regra importante

Na primeira fase, aprendizado deve produzir recomendações/priors
auditáveis.

Não deixar o sistema alterar pesos de produção automaticamente sem:

-   volume mínimo;
-   confidence;
-   versionamento;
-   rollback;
-   aprovação ou política explícita.

------------------------------------------------------------------------

# 21. Métricas operacionais e comerciais

Criar métricas por:

``` text
organization
campaign
offer_profile
offer_profile_version
provider
formula_version
```

Métricas mínimas:

``` text
candidates_discovered
candidate_to_lead_rate
prescoring_discard_rate
insufficient_data_rate
qualified_rate
precision_at_k
actionable_contact_rate
direct_contact_rate
reply_rate
positive_reply_rate
meeting_rate
proposal_rate
win_rate
cost_per_candidate
cost_per_qualified_lead
cost_per_actionable_contact
cost_per_meeting
```

Isso deve permitir comparar versões antes/depois.

------------------------------------------------------------------------

# 22. Observabilidade e auditoria

Cada execução importante deve ter trace/context:

``` text
organization_id
campaign_id
job_id
lead_id
offer_profile_key
offer_profile_version
plan_id
formula_version
```

Registrar:

``` text
provider called
duration
cost
quota
result count
error
skip reason
stop reason
```

Não logar secrets nem dados sensíveis desnecessários.

------------------------------------------------------------------------

# 23. Testes obrigatórios

Não considerar a fase concluída apenas com unit tests de helpers.

## 23.1 Unit

Testar:

-   profile resolver;
-   OfferMatcher;
-   pre-score;
-   intent decay;
-   trigger generation;
-   role matching;
-   confidence;
-   pattern states.

## 23.2 Integration

Testar:

``` text
OfferProfile → DiscoveryPlan
DiscoveryPlan → provider
Candidate → PreScore
Signals → OfferMatcher
Intent facts → Intent Engine
Company → Decision Maker Pipeline
```

## 23.3 End-to-end

Criar fixtures determinísticas para pelo menos:

### Landing Page

Clínica com:

-   Google ativo;
-   Instagram;
-   telefone;
-   sem site.

Esperado: forte oportunidade.

### Engenharia

Indústria com CNAE relevante + sinal de expansão.

Esperado: forte oportunidade para oferta técnica adequada.

### Troféus

Organização com competição anunciada e data futura.

Esperado: EventOpportunity + match alto para trophies.

### Negative case

Empresa sem evidência suficiente.

Esperado: `INSUFFICIENT_DATA`, e não falsa desqualificação.

------------------------------------------------------------------------

# 24. Organização de código

O diretório `services/` tende a crescer demais.

Planejar modularização por domínio, sem fazer refactor puramente
estético antes das capacidades funcionarem.

Sugestão futura:

``` text
services/workers/src/
├── prospecting/
│   ├── profiles/
│   ├── offers/
│   ├── scoring/
│   └── matching/
├── discovery/
│   ├── planner.py
│   ├── executor.py
│   └── providers/
├── signals/
├── intent/
│   └── providers/
├── contacts/
│   ├── decision_makers/
│   └── providers/
├── learning/
└── events/
```

Executar a migração incrementalmente.

Não fazer um "big bang refactor".

------------------------------------------------------------------------

# 25. Plano de migração por fases

## Fase A --- verdade documental

### Objetivo

Parar de chamar scaffolding de feature concluída.

### Fazer

-   corrigir status map;
-   revisar todos `*-FEITO.md`;
-   definir critérios COMPLETE/PARTIAL/SCAFFOLDING/PROPOSED;
-   atualizar architecture/context;
-   documentar entry point de cada capability.

### Não adicionar novas features nesta fase.

------------------------------------------------------------------------

## Fase B --- OfferProfile / Vertical Pack real

### Fazer

-   schemas;
-   versionamento;
-   resolver;
-   fallback por archetype;
-   migrar mappings;
-   criar profiles iniciais:
    -   landing_page;
    -   mechanical_project;
    -   technical_drawing;
    -   machine_manual;
    -   trophies.

### Critério

Adicionar nova oferta por configuração sem alterar engines centrais.

------------------------------------------------------------------------

## Fase C --- OfferMatcher

### Fazer

-   serviço;
-   score por oferta;
-   evidência;
-   persistência `LeadOpportunity`;
-   API/serialização se necessária;
-   testes.

### Critério

Uma empresa pode possuir múltiplas oportunidades simultâneas.

------------------------------------------------------------------------

## Fase D --- Discovery Planner executável

### Fazer

-   provider registry;
-   provider contract;
-   executor;
-   budgets;
-   CNAE mapping por oferta;
-   pipeline consumir plano.

### Critério

Alterar `OfferProfile.discovery` muda a estratégia de descoberta sem
editar `pipeline_worker`.

------------------------------------------------------------------------

## Fase E --- Intent real

### Fazer

-   IntentProvider contract;
-   WebsiteIntentProvider;
-   JobPostingIntentProvider;
-   novo scoring com decay;
-   trigger config por oferta.

### Critério

Um evento real coletado altera timing/intent da oportunidade com
evidência.

------------------------------------------------------------------------

## Fase F --- Troféus + Event Discovery

### Fazer

-   trophies OfferProfile;
-   EventOpportunity;
-   EventDiscoveryProvider;
-   sinais temporais;
-   organizer resolution;
-   timing.

### Critério

Sistema consegue transformar um evento futuro em oportunidade comercial
rastreável.

------------------------------------------------------------------------

## Fase G --- Decision Maker Resolution real

### Fazer

-   role resolver por OfferProfile;
-   PeopleDiscovery;
-   provider cascade;
-   identity resolution;
-   email/social discovery;
-   verification;
-   confidence;
-   routability.

### Critério

Pipeline retorna pessoa(s) reais ou um estado explícito de falha, não
apenas roles desejados.

------------------------------------------------------------------------

## Fase H --- Learning e métricas

### Fazer

-   outcomes;
-   métricas por oferta/provider;
-   dashboards;
-   priors;
-   comparação de versões.

### Critério

É possível provar se uma alteração aumentou ou reduziu a qualidade
comercial.

------------------------------------------------------------------------

# 26. Ordem de arquivos prioritários

Primeiro:

``` text
docs/melhorias/00-status-mapa.md
docs/melhorias/00-plano-melhorias-prospeccao.md
docs/00-plano-melhorias-prospeccao.md
docs/architecture.md
docs/context.md
```

Depois arquitetura de oferta:

``` text
services/workers/src/services/prospecting_profile_service.py
services/workers/src/services/archetype_service.py
services/workers/src/services/vertical_pack_service.py
services/workers/src/seeds/scoring_templates.py
```

Depois descoberta:

``` text
services/workers/src/services/discovery_planner_service.py
services/workers/src/services/cnae_discovery_service.py
services/api/src/pipeline_worker.py
```

Depois scoring/matching:

``` text
services/workers/src/services/candidate_pre_scoring_service.py
services/workers/src/services/offer_matcher_service.py
services/workers/src/services/signal_registry.py
```

Depois intent:

``` text
services/workers/src/services/intent_engine_service.py
services/workers/src/services/buying_trigger_service.py
```

Depois decisores:

``` text
services/workers/src/services/decision_maker_pipeline_service.py
services/workers/src/services/decision_maker_strategy_service.py
services/workers/src/services/company_person_service.py
services/workers/src/services/contact_provider_registry.py
services/workers/src/services/contact_enrichment_service.py
```

Depois eventos/learning.

------------------------------------------------------------------------

# 27. Coisas que NÃO devem ser feitas

## Não criar abstração sem consumidor

Todo novo registry/planner/interface precisa ter ao menos um fluxo real
consumindo-o.

## Não marcar helper como feature completa

Exemplo:

``` text
função retorna plano CNAE
```

não significa:

``` text
CNAE Discovery integrado
```

## Não duplicar inteligência comercial

Evitar:

``` text
ICP_BY_PROFILE
ROLE_BY_PROFILE
TRIGGER_BY_PROFILE
WEIGHTS_BY_PROFILE
```

espalhados.

Migrar para OfferProfile.

## Não usar LLM para substituir regra determinística

LLM é adequado para:

-   expansão semântica;
-   extração;
-   classificação textual;
-   geração de hipótese.

Não para:

-   thresholds;
-   quotas;
-   versionamento;
-   dedup;
-   state machine;
-   auditoria.

## Não esconder UNKNOWN

Ausência de informação não significa `false`.

## Não misturar FACT com INFERENCE

Manter contrato epistêmico em todas as novas features.

## Não automatizar aprendizado prematuramente

Primeiro medir, depois recomendar, só então permitir ajuste automático
controlado.

------------------------------------------------------------------------

# 28. Definition of Done global

Uma capability só recebe `COMPLETE` se:

-   [ ] possui contrato definido;
-   [ ] possui implementação não-placeholder;
-   [ ] está integrada ao pipeline;
-   [ ] possui configuração/versionamento quando aplicável;
-   [ ] possui evidência/provenance;
-   [ ] diferencia erro, ausência e desconhecido;
-   [ ] possui unit tests;
-   [ ] possui integration test;
-   [ ] possui ao menos um cenário realista;
-   [ ] possui observabilidade;
-   [ ] documentação corresponde ao código;
-   [ ] não depende de mapping hardcoded que deveria pertencer ao
    OfferProfile;
-   [ ] não afirma sucesso quando apenas enfileirou/tentou uma operação.

------------------------------------------------------------------------

# 29. Estado-alvo da arquitetura

``` text
Campaign
   │
   ▼
OfferProfile Resolver
   │
   ▼
Discovery Planner
   │
   ▼
Discovery Providers
   │
   ▼
Candidate Normalization + Dedup
   │
   ▼
Cheap Signals
   │
   ▼
Candidate Pre-Scoring
   │
   ▼
Lead / Candidate Promotion
   │
   ▼
Budgeted Enrichment
   │
   ├──────────────► Intent Providers
   │                      │
   │                      ▼
   │                 Intent Engine
   │
   ▼
Signal Registry
   │
   ├──────────────► Offer Matcher
   │                      │
   │                      ▼
   │                LeadOpportunity
   │
   ▼
Opportunity Vector
   │
   ▼
Decision Maker Resolution
   │
   ▼
Contact Discovery + Verification
   │
   ▼
Outreach Recommendation
   │
   ▼
Sales Outcome
   │
   ▼
Learning / Metrics
```

Para oportunidades temporais:

``` text
Event Discovery
      │
      ▼
EventOpportunity
      │
      ▼
Organizer Resolution
      │
      ▼
Signals
      │
      ▼
Offer Matcher
      │
      ▼
Trophies / other temporal offers
```

------------------------------------------------------------------------

# 30. Resultado esperado

Ao concluir este plano, o sistema não deve ser apenas um conjunto de
serviços genéricos de prospecção.

Ele deve conseguir responder, de forma auditável:

1.  **Que tipo de empresa/organização devemos procurar para esta
    oferta?**
2.  **Em quais fontes devemos procurar?**
3.  **Por que este candidato vale enriquecimento?**
4.  **Quais fatos sabemos sobre ele?**
5.  **Quais conclusões são inferências?**
6.  **Qual oferta faz mais sentido para esta organização?**
7.  **Existe algum motivo para abordar agora?**
8.  **Quem provavelmente participa da decisão?**
9.  **Temos um contato real e verificável?**
10. **Qual canal deve ser usado?**
11. **Qual evidência deve aparecer na abordagem?**
12. **Essa estratégia está realmente convertendo?**

O objetivo final não é aumentar a quantidade de classes, services ou
documentos.

O objetivo é transformar:

``` text
dados públicos
```

em:

``` text
oportunidade comercial
+ evidência
+ timing
+ decisor
+ contato
+ aprendizado
```

com custo controlado, comportamento explicável, suporte a múltiplas
ofertas e evolução baseada em resultados reais.

------------------------------------------------------------------------

# 31. Prioridade final

Se o trabalho precisar ser dividido em PRs curtos, a sequência
recomendada é:

``` text
PR 1  — corrigir status/documentação
PR 2  — schema + resolver de OfferProfile
PR 3  — migrar regras hardcoded para OfferProfile
PR 4  — OfferMatcher + LeadOpportunity
PR 5  — DiscoveryProvider contract + executor
PR 6  — DiscoveryPlanner orientado por oferta
PR 7  — CNAE mapping por oferta
PR 8  — IntentProvider contract + scoring temporal
PR 9  — Website/Jobs intent collectors
PR 10 — trophies OfferProfile
PR 11 — EventOpportunity + Event Discovery
PR 12 — Decision Maker pipeline executável
PR 13 — Contact cascade + verification
PR 14 — métricas/outcomes/learning
PR 15 — limpeza final de scaffolding e atualização dos docs
```

Cada PR deve preservar compatibilidade, adicionar testes e atualizar o
status somente das capacidades efetivamente entregues.

------------------------------------------------------------------------

# 32. Resultado da auditoria final (2026-09-04)

A auditoria final confirmou que o código das Fases B–H está presente e possui
testes focados, mas não que todas as capacidades sejam operacionais de ponta a
ponta. O critério desta seção é mais rigoroso: um módulo só é `COMPLETE` se
tiver caller de produção, persistência/provider aplicável e observabilidade
mínima.

## Evidências

- O grafo foi regenerado com `graphify extract --code-only` (4.893 nós, 11.045
  arestas).
- 117 testes focados C–H passaram com `-W error` após as correções desta
  auditoria.
- `py_compile` dos módulos alterados passou e `git diff --check` não encontrou
  whitespace inválido.
- O E2E de outreach foi **skipped** sem `E2E_DATABASE_URL`; não é evidência de
  que o fluxo com banco passou.
- A migration `e8f9a0b1c2d3` adiciona `notifications` e foi aplicada no banco
  local; `alembic check` ainda lista divergências históricas de metadata/índices
  fora do escopo desta correção.

## Classificação final

| Capability | Status | Motivo |
|---|---|---|
| OfferProfile/Resolver | `PARTIAL` | Existe e é testado, mas o pipeline ainda usa `CampaignScoringTemplate`/resolver legado. |
| OfferMatcher | `PARTIAL` | Integrado ao enrichment e persistido em `evidence_score`; falta tabela/API de oportunidades. |
| Discovery Executor | `PARTIAL` | Contrato/adapters existem; `pipeline_worker` ainda chama providers diretamente. |
| Intent Provider | `SCAFFOLDING` | Não há collector/job de produção conectado ao IntentEngine. |
| Event Discovery | `SCAFFOLDING` | Provider esportivo é injetado/testável; não há fonte externa persistida. |
| Decision Maker Resolution | `PARTIAL` | Chamado pelo enriquecimento e salvo em JSONB; entidade de pessoa ainda não é o resultado canônico. |
| Learning & Metrics | `SCAFFOLDING` | Registry in-memory sem endpoint, persistência ou dados comerciais reais. |

## Correções aplicadas

- APIs síncronas de discovery/eventos agora aguardam providers async mesmo com
  loop ativo, usando thread isolada sem descartar dados nem gerar warnings.
- `OfferProfile.from_dict` respeita defaults de dataclass e o registry remove
  índices secundários obsoletos em re-registro.
- `OfferMatcher` passou a ser executado no pós-scoring e gravado no JSONB de
  evidências.
- Removido o registro indevido de `QUALIFIED/MEETING/WON` durante scoring;
  outcomes só devem nascer de eventos comerciais reais.
- `ContactVerification` passou a usar `EmailVerificationService.verify_email`,
  método público existente, em vez de `check_domain_mx` inexistente.
- Resolução de decisores passou a persistir em `Lead.evidence_score`; `Lead`
  não possui `raw_data`.

O status atualizado e a matriz de capabilities estão em
`docs/00-status-mapa.md`. Os próximos marcos são integração do resolver e do
executor async no pipeline, migrations de oportunidades/eventos/outcomes,
collectors reais e um E2E de banco que percorra toda a cadeia comercial.
