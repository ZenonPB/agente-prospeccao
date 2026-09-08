# Mapa de pendências pós-consolidação — revisão atualizada

> **Objetivo:** registrar apenas o que ainda falta implementar, validar, integrar, persistir ou tornar operacional no sistema atual.
>
> **Base da revisão:** estado atual do repositório no branch `feat/identidade-cross-provider`, incluindo código, migrations, rotas, persistência, UI e testes existentes.
>
> **Regra principal:** uma capacidade não deve ser chamada de concluída apenas porque existe classe, helper, registry, teste unitário ou retorno estruturado. Para ser **Operacional**, precisa existir no fluxo real, com persistência quando necessária, tenant scope, estados de erro explícitos, observabilidade e comportamento verificável.
>
> Este documento substitui o mapa anterior de pendências como referência operacional. Ele **não** substitui `docs/00-status-mapa.md`; os dois devem ser mantidos sincronizados.

> **Snapshot:** 2026-09-07 · `944 passed` com `-W error` · `compileall`, lint,
> TypeScript, build Web e migration verifier verdes · Alembic head
> `dd9e0f1a2b3c`.

## Resumo desta revisão

### Fechado nesta branch

- P0.1–P0.5: E2E/persistência PostgreSQL controlada, migrations verificadas,
  política de warnings, documentação sincronizada e observabilidade de
  providers completa (correlation IDs + tokens/custo Groq + endpoint de trace).
- P1.15: provider HTTP opt-in de eventos com retry, Bearer opcional, validação
  de payload e distinção entre `ok`, `empty`, `failed` e `skipped`.
- P1.16: evento → organizador → `Company`/`Lead`, com deduplicação e provenance.
- P1.19: status `upcoming`/`expired`, expiração idempotente e scheduler; estados
  adicionais continuam reservados para fontes que os declararem.
- P1.22–P1.24: atribuição explícita de oferta/versão/oportunidade em outcomes e
  conversões, com fallback `unknown` revisável.
- P1.30: comparação A/B com Wilson, amostra mínima, persistência, endpoint,
  aprovação humana e auditoria.

### Ainda falta

- identidade cross-provider de empresas e provenance genérica de Candidate/Lead;
- schema semântico e administração de `OfferProfile`;
- evento → decisor → outreach (a etapa evento → `OfferMatcher` → oportunidade já está operacional);
- provider real especializado de vagas e intent;
- BI por vertical/consultor/canal/etapa/variante e Precision@K operacional;
- entidade canônica e pipeline completo de decisores;
- exploração controlada, recorrência de eventos, janela ideal aprendida e
  operação em devices reais.

### Mapa rápido de execução

| Item | Status atual | Observação |
|---|---|---|
| P0.1 E2E/persistência PostgreSQL controlada | ✅ Feito | Ciclo persistente e testes controlados verdes; E2E externo com credenciais reais continua opcional. |
| P0.2 Migrations/head/schema | ✅ Feito | `verify_migrations.py` confirma head `dd9e0f1a2b3c`. |
| P0.3 Warnings Python | ✅ Feito | Suíte verde com `-W error`. |
| P0.4 Documentação de estado | ✅ Feito | `context`, status e este mapa sincronizados nesta revisão. |
| P0.5 Observabilidade agregada | ✅ Feito | `correlation_id`/`campaign_id`/`usage`/`cost` persistidos; telemetria de tokens Groq; endpoint `provider-trace` org-scoped explica "poucos leads". |
| P1.15–P1.16 Event Discovery/provider → Lead | ✅ Feito | Provider confiável, dedup, provenance e vínculo org-scoped. |
| P1.19 Expiração de eventos | ✅ Feito | `upcoming`/`expired`, TTL ISO normalizado para UTC e job idempotente. |
| P1.22–P1.24 Atribuição comercial | ✅ Feito | Oferta, versão e oportunidade persistidas. |
| P1.25 BI por oferta/período | 🟠 Parcial | Oferta/versão/período/amostra prontos; cortes avançados faltam. |
| P1.30 A/B estatístico | ✅ Feito | Wilson, persistência, aprovação humana e auditoria. |
| P1.17 Evento → oferta | ✅ Operacional | Evento futuro com lead resolvido gera `trophies` via `OfferMatcher`; decisor/outreach seguem na P1.18. |
| P1.18 Evento → decisor/outreach | 🟠 Parcial | Ação recomendada persiste contato/canal quando já há decisor; descoberta externa e outreach ainda faltam. |
| P1.31 Entidade canônica de pessoa | 🟠 Parcial | Metadados de confiança e acionabilidade persistidos em `Contact`; entidade canônica independente ainda falta. |
| P1.32 Identity confidence sem CPF | ✅ Operacional | Score de evidências persistido; CPF/QSA continua forte, mas não obrigatório. |
| P1.33 Source Reliability | ✅ Operacional | Registry calibrável integrado ao cálculo de confiança. |
| P1.34–P1.38 People Discovery/decisores | 🟠 Parcial | Contatos e ação recomendada existem; discovery externo e cascade completa ainda faltam. |
| P1.39 Routable contact | 🟠 Parcial | Classificação persistida e exposta; integração efetiva à cadência ainda falta. |
| P2.1–P2.2 OfferProfile administrativo | 🟠 Parcial | Perfis ainda são registrados em código. |
| P2.6 QA em device real | ⬜ Planejado | Falta execução em celular/tablet real. |

---

# 1. Legenda de status

| Status | Significado |
|---|---|
| ✅ **Operacional** | Fluxo real integrado, persistido quando necessário, testado e observável. |
| 🟠 **Parcial** | Existe comportamento real, mas falta parte relevante para uso confiável em produção. |
| 🔵 **Estrutural** | Existe contrato, classe, helper ou infraestrutura, mas o fluxo principal ainda não entrega a capacidade de ponta a ponta. |
| ⬜ **Planejado** | Ainda não existe implementação funcional relevante. |
| ⏸ **Adiado** | Foi conscientemente removido do escopo atual; só reabrir com decisão explícita de produto. |

---

# 2. O que já está realmente operacional e deve ser preservado

As seguintes fundações **não são backlog principal**. Mudanças futuras devem preservar o comportamento e a compatibilidade:

- scoring contextual com `CampaignScoringTemplate`;
- pre-scoring determinístico antes de enriquecimento pesado;
- auditoria de descartes em `prescoring_discards`;
- Signal Registry/status epistêmico;
- enrichment adaptativo por capabilities;
- `OfferProfile` declarativo e resolver com fallback legado;
- `OfferMatcher`;
- persistência relacional de múltiplas ofertas em `lead_opportunities`;
- endpoint de oportunidades do lead;
- `DiscoveryExecutor` com adapters de Places/CNAE e execução assíncrona;
- Google Places multi-query;
- CNAE discovery;
- `EventOpportunityRow` e persistência de eventos;
- `CommercialOutcomeRow` e outcomes comerciais básicos;
- isolamento multi-tenant das rotas novas;
- jobs do pipeline e WebSocket autenticado;
- trilha de atividades do lead;
- cadência e humano no loop;
- BI comercial básico;
- OfferProfiles iniciais:
  - `landing_page`;
  - `mechanical_project`;
  - `technical_drawing`;
  - `machine_manual`;
  - `trophies`.

Essas capacidades podem possuir pendências de **qualidade, observabilidade, atribuição ou extensão**, mas não devem ser reescritas sem necessidade.

---

# 3. P0 — Validação operacional antes de novas grandes features

## P0.1 — Executar E2E real com PostgreSQL

**Status:** ✅ Operacional

### Estado atual

A suíte e os testes de persistência cobrem o ciclo controlado em PostgreSQL, incluindo eventos, outcomes, atribuição e migrations. O E2E externo completo com credenciais reais continua sendo uma validação operacional posterior:

```text
Campanha
→ Job
→ Discovery
→ Candidate
→ Pre-score
→ Lead
→ Enrichment
→ Scoring
→ LeadOpportunity
→ Decision Maker
→ Mensagem
→ Cadência
→ Resposta
→ Conversão
→ CommercialOutcome
→ BI
```

### O que fazer

Executar `tests/e2e_outreach_cycle.py` em ambiente controlado com:

- `E2E_DATABASE_URL`;
- migrations aplicadas;
- organização/usuário fixture;
- providers externos stubados ou credenciais de teste;
- Groq/SMTP simulados;
- WebSocket validado.

### Critérios de aceite

- execução repetível do ciclo completo;
- nenhuma dependência de banco SQLite quando o comportamento real depende de PostgreSQL;
- erro em qualquer etapa gera estado/log identificável;
- execução pode ser reproduzida no CI ou em job manual de validação.

### Arquivos/áreas

```text
tests/e2e_outreach_cycle.py
services/api/src/pipeline_worker.py
services/api/src/routes/pipeline.py
services/api/src/jobs_consumer.py
services/workers/migrations/
.github/workflows/
```

---

## P0.2 — Validar migrations do zero e incrementalmente

**Status:** ✅ Operacional

### Estado atual

O verificador automatizado e a validação PostgreSQL controlada confirmam:

- head único `fe4f5a6b7c8d`;
- tabelas, índices, FKs e constraints essenciais;
- upgrade incremental a partir do head anterior;
- compatibilidade com instalação parcialmente provisionada.

### Limitação restante

Uma execução de banco limpo e rollback destrutivo continuam sendo atividades de
QA descartável, não requisito do fluxo de produção:

1. banco limpo → `alembic upgrade head`;
2. banco em versão anterior suportada → upgrade incremental;
3. inspeção das tabelas novas:
   - `lead_opportunities`;
   - `event_opportunities`;
   - `commercial_outcomes`;
   - `prescoring_discards`;
4. constraints/índices/FKs;
5. rollback apenas em banco temporário.

### Critério de aceite

CI ou script de QA prova a sequência.

---

## P0.3 — Resolver warnings incompatíveis com Python suportado

**Status:** ✅ Operacional

### Estado atual

O filtro específico para a depreciação upstream está aplicado e a suíte atual
passa sob `-W error`; não há warning da aplicação sendo escondido globalmente.

### Política mantida

Enquanto a dependência upstream não corrige a chamada, manter a política
específica:

- atualizar dependência;
- fixar versão Python oficialmente suportada;
- aplicar política explícita de warning conhecido;
- substituir dependência se necessário.

### Critério de aceite

```bash
python -W error -m pytest tests -q
```

passa no ambiente oficialmente suportado.

---

## P0.4 — Sincronizar documentação estrutural com o código atual

**Status:** ✅ Operacional

### Estado atual

**✅ Fechado nesta revisão documental.** `context.md`, `architecture.md`,
`offer-profile.md` e `00-status-mapa.md` agora descrevem o fluxo real; este
arquivo permanece como backlog; `consolidacao.md` e `roadmap-vendas.md` estão
marcados como histórico/roadmap. O critério de manutenção é que documentos
históricos não sejam usados como fonte do status atual.

### Critério de manutenção

Um agente novo deve conseguir responder corretamente:

```text
quem resolve OfferProfile?
quem executa discovery?
onde oportunidades são persistidas?
onde eventos são persistidos?
como outcomes são atribuídos?
qual parte de decisores ainda é parcial?
```

sem encontrar respostas contraditórias nas fontes operacionais.

---

## P0.5 — Observabilidade mínima de providers e jobs

**Status:** ✅ Operacional (onda 0)

### Problema

Vários fluxos ainda tratam falha de provider como `[]`/`continue`.

Isso faz situações diferentes parecerem iguais:

```text
provider funcionou e encontrou zero
provider falhou
provider não estava configurado
quota acabou
```

### O que implementar

Criar um resultado padrão de execução:

```json
{
  "provider": "cnae_discovery",
  "status": "success|empty|failed|disabled|quota_exceeded|skipped",
  "result_count": 12,
  "duration_ms": 830,
  "budget_used": 12,
  "error_code": null,
  "retryable": false
}
```

### Métricas mínimas

- `provider_success_rate`;
- `provider_failure_rate`;
- `provider_empty_rate`;
- `provider_latency_ms`;
- `provider_quota_used`;
- `job_duration`;
- `job_failure_stage`;
- `offer_profile_fallback_rate`;
- `prescoring_discard_rate`;
- `prescoring_insufficient_data_rate`.

### Arquivos

```text
services/workers/src/services/prospecting/discovery_executor.py
services/workers/src/services/prospecting/event_discovery.py
services/workers/src/services/prospecting/intent_provider.py
services/api/src/pipeline_worker.py
services/workers/src/services/provider_client.py
```

### Critério de aceite

A operação consegue explicar **por que uma campanha trouxe poucos leads**.

### O que foi entregue

- `provider_execution_metrics` persiste `correlation_id`, `campaign_id` e
  `usage` (JSONB), preenchendo também `cost` (estimativa USD por modelo).
- Discovery (Places/CNAE), Event Discovery e scoring Groq emitem métricas por
  execução, correlacionadas por `correlation_id` e `campaign_id`.
- `groq_json_chat` expõe `on_usage` (tokens prompt/completion) via callback,
  sem alterar os chamadores existentes.
- `run_pipeline` gera um `correlation_id` por execução, loga na abertura do
  job, propaga para toda telemetria e devolve `correlation_id` +
  `provider_metrics` agregadas no payload final do WebSocket/job.
- Endpoint `GET /analytics/provider-trace/{correlation_id}` (org-scoped)
  devolve todas as medições de uma execução — incluindo status, latência,
  erro, custo e tokens — respondendo ao critério de aceite.
- Nova migration `ee5f6b7c8d0a` (head) adiciona `correlation_id`,
  `campaign_id` e `usage`. Índice por `correlation_id`.

---

# 4. P1 — Discovery e resolução de entidades

| P1.1 Cross-provider Company Identity Resolution | ✅ Operacional | Resolve por CNPJ → domínio → aliases (`company_aliases`) na Company antes de criar Lead (Places, CNAE, PNCP); merge fuzzy continua apenas candidato. |

**Status:** ✅ Operacional

Entregue no PR 03: `company_aliases` registra chaves externas (place_id,
domínio, maps_uri) por Company; `CompanyPersonService` resolve por
CNPJ → domínio → aliases e faz backfill; o pipeline consulta a Company antes de
criar Lead nas rotas Places, CNAE e PNCP, mesclando provenance das fontes. O
match fuzzy (nome + cidade/UF) permanece apenas candidato para revisão humana.

### Problema

O `DiscoveryExecutor` deduplica usando chaves simples. Uma mesma empresa pode aparecer como:

```text
Places:
Metalúrgica XPTO
place_id = abc

CNAE:
METALURGICA XPTO LTDA
cnpj = 00...

PNCP:
XPTO INDUSTRIA
cnpj = 00...
```

Sem resolução de identidade entre fontes:

- podem surgir leads duplicados;
- evidências ficam divididas;
- enrichment é repetido;
- custo aumenta;
- aprendizado fica contaminado.

### Ordem de identidade recomendada

```text
CNPJ exato
→ normalized_domain
→ place_id
→ nome normalizado + cidade/UF
→ fuzzy apenas como candidato de merge
```

### O que fazer

Criar uma camada de identidade no discovery antes da promoção para Lead.

A camada `CompanyIdentityResolver` agora confirma chaves fortes, marca nomes e
localização como candidatos sem merge automático e preserva a provenance das
fontes combinadas.

Preferir reaproveitar `CompanyPersonService` / normalização existente, em vez de criar outro resolver independente.

### Critério de aceite

Candidato vindo de Places e CNAE para a mesma empresa vira uma entidade única e preserva provenance das duas fontes.

### Arquivos

```text
services/workers/src/services/prospecting/discovery_executor.py
services/workers/src/services/company_person_service.py
services/workers/src/services/domain_utils.py
services/api/src/pipeline_worker.py
```

---


**Status:** 🟠 Parcial — provenance consolidada já é persistida em `Lead`; ainda
falta histórico por candidato rejeitado e resolução cross-provider completa.

O campo `Lead.discovery_provenance` preserva providers, consultas, identificadores
externos, plano de discovery e regra de identidade. Candidatos rejeitados pelo
pre-scoring ainda não têm esse histórico completo.

### Problema

O sistema já preserva várias evidências, mas a origem do discovery precisa ficar consistente para auditoria e learning.

### Persistir

```text
provider
provider_query
provider_candidate_id
retrieved_at
discovery_plan_id
matched_identity_rule
```

### Objetivo

Permitir responder:

> “Este lead foi descoberto por qual fonte e por qual consulta?”

e:

> “Qual provider gera leads que realmente convertem?”

---

## P1.3 — Selection bias do pre-scoring

**Status:** ⬜ Planejado

### Problema

Quando apenas o top-K é enriquecido, o sistema só aprende com candidatos que o modelo atual já considera bons.

Isso pode impedir descobrir segmentos de lead bons que o pre-score inicial penaliza.

### Evolução futura controlada

Adicionar modo de exploração opcional:

```text
95% exploitation = top score
5% exploration = elegíveis fora do top-K
```

Somente quando houver volume suficiente.

### Importante

Não ativar por padrão ainda.

Primeiro medir:

```text
prescoring_discard → revisão → qualidade posterior
```

---

# 5. P1 — OfferProfile e inteligência por oferta

## P1.4 — Validar schema semanticamente

**Status:** 🔵 Estrutural

### Problema

`OfferProfile` usa vários `Dict[str, Any]`. Isso facilitou a evolução, mas permite configurações inválidas como:

- provider inexistente;
- signal inexistente;
- weight inválido;
- threshold fora da faixa;
- decision maker vazio;
- `event_weight` fora de `[0,1]`;
- enrichment step desconhecido.

### O que criar

`OfferProfileValidator` ou Pydantic schema equivalente.

### Validar

```text
profile.key
version
provider keys
signal keys
prescoring thresholds
weights
intent config
decision maker roles
channel keys
enrichment steps
```

### Quando executar

- seed/startup;
- teste;
- publicação futura de profile;
- criação administrativa futura.

### Arquivos

```text
services/workers/src/services/prospecting/offer_profile.py
services/workers/src/services/prospecting/default_profiles.py
services/workers/src/services/enrichment_capability_registry.py
services/workers/src/services/signal_registry.py
```

---

## P1.5 — Reduzir dupla fonte da verdade OfferProfile × template legado

**Status:** 🟠 Parcial

### Problema

Hoje o pipeline resolve `OfferProfile`, mas ainda traduz parte dele para um `scoring_template` compatível com código legado.

Isso é adequado como migração, mas não deve ser permanente.

### Estado desejado

```text
OfferProfile
= estratégia comercial

CampaignScoringTemplate
= política/prompt específico do AIScoringService
```

O template não deve duplicar:

- ICP;
- discovery strategy;
- decision makers;
- intent;
- channels.

### O que fazer

1. adicionar telemetria de uso de fallback;
2. identificar campos duplicados;
3. migrar consumidores;
4. só remover legado após cobertura.

### Não fazer

Não apagar `CampaignScoringTemplate` abruptamente.

---

## P1.6 — Administração de OfferProfile continua P2

**Status:** 🟠 Parcial

Profiles ainda ficam em `default_profiles.py`.

Isso **não é problema urgente**.

Antes de construir editor, estabilizar:

- schema;
- campos;
- versionamento;
- learning;
- rollback.

A UI administrativa deve permanecer P2.

---

# 6. P1 — OfferMatcher e LeadOpportunity

## P1.7 — Melhorar score do OfferMatcher

**Status:** 🟠 Parcial

### Problema

O algoritmo atual é simples:

```text
signals positivos → até 70
ICP hits → até 30
```

Isso é bom como baseline, mas insuficiente para tornar o matching excepcional.

Limitações:

- todos signals positivos têm peso igual;
- ICP hits têm peso fixo;
- `UNKNOWN` e `false` ainda podem ficar próximos semanticamente;
- Intent não entra no match;
- source reliability não entra;
- commercial outcomes ainda não calibram o match.

### Estado desejado

Score por oferta deve considerar separadamente:

```text
icp_fit
need
intent
buying_power
reachability
timing
```

O matcher pode continuar simples, mas `LeadOpportunity.overall` deve vir de política versionada por OfferProfile.

### Critério de aceite

`mechanical_project`, `technical_drawing` e `machine_manual` atribuem pesos diferentes aos mesmos sinais.

---

## P1.8 — Snapshot histórico da LeadOpportunity

**Status:** 🟠 Parcial

### Problema

`LeadOpportunityService.replace_opportunities()` atualiza/remove o conjunto atual.

Isso é correto para a visão atual do lead, mas pode perder o contexto de como a oportunidade era avaliada no momento de:

- contato;
- reunião;
- proposta;
- venda.

### O que falta

Persistir histórico/auditoria:

```text
offer_profile_version
formula_version
profile_snapshot_hash
scored_at
signals_snapshot
evidence_snapshot
```

Opções:

- tabela de histórico;
- append-only snapshots;
- CommercialOutcome apontar para snapshot imutável.

### Critério de aceite

Uma mudança de profile v1.0 → v1.1 não altera retroativamente o contexto da venda antiga.

---

## P1.9 — Política explícita de re-scoring

**Status:** ⬜ Planejado

Definir comportamento quando uma nova versão de OfferProfile é publicada:

- oportunidades existentes **não** devem mudar automaticamente;
- novas coletas usam nova versão;
- campanha ativa pode receber `reanalyze` explícito;
- histórico antigo permanece preservado.

Documentar em:

```text
docs/decisions.md
docs/business-rules.md
```

---

## P1.10 — “Why this offer?” na API/UI

**Status:** 🟠 Parcial

O sistema já tem evidências, mas precisa apresentar uma justificativa comercial por oportunidade.

### Estado atual

O endpoint e a UI já expõem `evidence`, `signals_matched` e `signals_missing` por
`LeadOpportunity`. Continua faltando separar explicitamente fato, hipótese e
pergunta de validação em uma narrativa comercial completa.

Exemplo:

```text
Desenho Técnico — 91

FATOS:
- atua com usinagem
- fabrica peças sob encomenda
- possui operação CNC

HIPÓTESE:
- pode existir demanda por detalhamento externo

VALIDAÇÃO:
- perguntar se desenhos são feitos 100% internamente
```

### O que fazer

Ligar:

```text
LeadOpportunity
+ evidence
+ epistemic status
+ discovery_questions
```

### Objetivo

Transformar o sistema em **copiloto de vendas**, não apenas ranking.

---

# 7. P1 — Intent Collection real

## P1.11 — JobPosting Intent Provider conectado a fonte real

**Status:** 🟠 Parcial

### Hoje

`JobPostingIntentProvider` interpreta vagas fornecidas no contexto.

### Falta

Uma fonte real que encontre vagas automaticamente.

### Prioridade

Essa deve ser a primeira coleta externa de intent porque atende diretamente:

- Engenharia Mecânica;
- ERP;
- Sistemas Web.

### Signals úteis para Engenharia

```text
HIRING_MECHANICAL_ENGINEER
HIRING_PROJECT_DESIGNER
HIRING_MAINTENANCE
HIRING_AUTOMATION
HIRING_CNC_OPERATOR
HIRING_PRODUCTION_ENGINEER
```

### Requisitos

Todo evento precisa:

```text
source
source_url
observed_at
event_at
confidence
TTL
provider_status
```

### Regra

`provider falhou` != `nenhuma vaga encontrada`.

---

## P1.12 — Website Semantic Intent específico por oferta

**Status:** 🟠 Parcial

O provider de site existe, mas a inteligência de Engenharia ainda precisa de sinais mais específicos.

### Criar/extrair

```text
HAS_CNC
OFFERS_USINAGEM
OFFERS_CALDEIRARIA
MANUFACTURES_CUSTOM_EQUIPMENT
HAS_ENGINEERING_DEPARTMENT
HAS_MAINTENANCE_OPERATION
CUSTOM_PARTS
PRODUCT_DEVELOPMENT
USES_CUSTOM_MACHINERY
HAS_PRODUCTION_LINE
```

### Por oferta

#### `mechanical_project`

Priorizar:

```text
custom machinery
production line
automation
new equipment
engineering
```

#### `technical_drawing`

Priorizar:

```text
usinagem
custom parts
replacement parts
reverse engineering
technical drawing
```

#### `machine_manual`

Priorizar:

```text
machine manufacturer
NR-12
equipment delivery
industrial safety
technical documentation
```

### Arquivos

```text
services/workers/src/services/prospecting/intent_provider.py
services/workers/src/services/signal_registry.py
services/workers/src/services/prospecting/default_profiles.py
services/workers/src/services/technical_enrichment_service.py
```

---

## P1.13 — Outros Intent Providers

**Status:** ⬜ Planejado

Após vagas:

1. `CompanyNewsIntentProvider`;
2. `ProcurementIntentProvider`;
3. `SocialIntentProvider`.

Não implementar todos ao mesmo tempo.

Priorizar conforme dados comerciais.

---

## P1.14 — Calibrar intent com outcomes

**Status:** 🔵 Estrutural

Medir:

```text
P(REPLIED | signal)
P(MEETING | signal)
P(WON | signal)
```

por:

```text
organization
offer_key
offer_version
signal_key
```

Objetivo: descobrir se sinais intuitivamente fortes realmente convertem.

---

# 8. P1 — Troféus e Event Discovery

## P1.15 — Provider real de eventos

**Status:** ✅ Operacional — provider HTTP opt-in

### Hoje

`EVENT_DISCOVERY_URL` habilita provider HTTP opt-in.

O adapter já possui timeout, retry limitado, Bearer opcional, validação de
payload, provenance e estados `ok`/`empty`/`failed`/`skipped`. A pendência é
operar fontes especializadas além do endpoint HTTP genérico.

### Limitação restante

Ainda falta selecionar e operar fontes especializadas (MEJ/esportes/etc.) além
do endpoint HTTP configurável. O contrato, retry, auth, provenance, validação e
distinção `failed`/`empty` já estão implementados.

### Estratégia recomendada

Não depender eternamente de um único endpoint genérico.

Criar providers especializados progressivamente:

```text
MejEventProvider
SportsEventProvider
AcademicEventProvider
CorporateAwardsProvider
```

### Primeira prioridade para AlphaMec

**MEJ**.

Porque existe:

- histórico comercial;
- prova social;
- rede;
- recorrência;
- decisão acessível.

### Requisitos de provider

- timeout;
- retries;
- auth;
- rate limit;
- provenance;
- schema validation;
- monitoramento;
- `failed` diferente de `empty`.

---

## P1.16 — Evento → organizador → Lead

**Status:** ✅ Operacional com revisão para baixa confiança

### Hoje

O evento guarda:

```text
organizer
organizer_resolved
lead_id nullable
```

O vínculo já é resolvido e persistido quando a resolução tem confiança mínima;
casos ambíguos permanecem explícitos e revisáveis.

### Estado atual

O serviço resolve ou cria de modo idempotente quando há resolução confiável e
persiste `lead_id` e provenance. Organizadores sem evidência suficiente ficam
explicitamente sem lead; a resolução de CNPJ/fuzzy cross-provider continua
pendente.

Fluxo implementado:

```text
event organizer
→ identidade da organização
→ lead existente?
→ criar candidate/lead?
→ associar EventOpportunity.lead_id
```

### Regras

- dedup obrigatório;
- provenance da associação;
- não criar empresa fictícia se organizador não puder ser resolvido;
- estado explícito:

```text
resolved
ambiguous
not_found
failed
```

---

## P1.17 — Evento → OfferMatcher → oportunidade

**Status:** ✅ Operacional para eventos futuros com lead resolvido

Evento não deve parar em relatório. Eventos futuros com lead resolvido agora são
processados pelo `EventOpportunityService` e persistidos como oportunidade de
`trophies` usando o `OfferMatcher` existente.

Fluxo desejado:

```text
EventOpportunity
→ organizer Lead
→ signals temporais
→ OfferMatcher
→ LeadOpportunity(trophies)
→ timing
```

### Critério de aceite

Evento futuro com organizador resolvido gera oportunidade comercial rastreável
para troféus, com versão, evidências temporais e operação idempotente. Eventos
sem lead ou expirados ficam explicitamente ignorados; decisor e outreach não são
disparados automaticamente.

---

## P1.18 — Evento → decisor → ação comercial

**Status:** 🟠 Parcial

Após resolver organizador e, quando disponível, selecionar um contato persistido:

```text
OfferProfile.trophies.decision_makers
→ People Discovery
→ Decision Maker Resolution
→ canal
→ próxima ação
```

O backend agora persiste a recomendação quando há contato acionável. A UI deve mostrar:

```text
Evento
Data
Timing
Organizador
Oferta
Decisor
Confiança
Canal
Próxima ação
```

Envio continua humano no loop por padrão.

---

## P1.19 — Estados e expiração de evento

**Status:** ✅ Operacional para `upcoming`/`expired`

Estados implementados:

```text
upcoming
expired
```

`cancelled`, `unknown` e `completed` ficam reservados para providers que
entregarem esses estados, recorrência ou cancelamento explícito.

### Regras

- evento expirado não cria nova ação;
- histórico permanece;
- cleanup/archiving mensurável;
- alteração de data não cria duplicata automaticamente.

---

## P1.20 — EventSeries / recorrência

**Status:** ⬜ Planejado

### Importância

Troféus têm alto potencial de recompra.

Eventos como:

```text
ENEJ 2025
ENEJ 2026
ENEJ 2027
```

não devem ser tratados como independentes para sempre.

### Criar

Opção A: entidade `EventSeries`.

Opção B: campos em EventOpportunity:

```text
series_key
recurrence_confidence
previous_event_id
expected_next_window
```

### Objetivo

Gerar:

```text
RECURRENT_EVENT
EXPECTED_REBUY_WINDOW
```

e reabrir oportunidade automaticamente perto da janela ideal.

---

## P1.21 — Aprender janela ideal de contato para troféus

**Status:** ⬜ Planejado

O `EventTimingScorer` atual usa heurística fixa.

Com dados reais, calcular:

```text
data primeiro contato
data fechamento
data evento
quantidade
tempo produção
tempo aprovação/prototipagem
```

Produzir:

```text
optimal_contact_window_by_offer
```

Isso deve substituir gradualmente heurística fixa.

---

# 9. P1 — Outcomes comerciais e atribuição correta

## P1.22 — Nova conversão deve informar a oferta explicitamente

**Status:** ✅ Operacional para novas conversões

### Política atual

Novas conversões não inferem silenciosamente a oportunidade de maior score.

Essa era a falha histórica que poderia atribuir venda à oferta errada; novas
conversões já não usam esse fallback silencioso.

Exemplo:

```text
Landing Page score 90
ERP score 75
venda real = ERP
```

O fallback registraria Landing Page.

### Mudança

Para **novas conversões**:

- `offer_key` obrigatório **ou**
- `unknown` explícito e revisável.

Fallback por maior score apenas para dados históricos/migração.

### Arquivos

```text
services/api/src/routes/leads.py
services/workers/src/database/models.py
services/workers/src/services/prospecting/commercial_outcome_service.py
apps/web/src/components/oportunidades/conversion-dialog.tsx
apps/web/src/types/
```

---

## P1.23 — Associar CommercialOutcome à LeadOpportunity

**Status:** ✅ Operacional

Campos persistidos:

```text
lead_opportunity_id nullable
```

em `commercial_outcomes`, com FK e escopo da organização.

### Benefício

Rastreabilidade exata:

```text
lead
+
oferta
+
versão
+
score
+
evidências
```

que originaram a venda.

---

## P1.24 — Conversion também deve carregar offer_key/version

**Status:** ✅ Operacional

Além dos campos humanos, `Conversion` agora guarda:

```text
service_sold
contract_value
offer_key
offer_version
lead_opportunity_id
```

Mantendo `service_sold` como descrição humana.

---

# 10. P1 — Learning e BI

## P1.25 — BI por oferta/versão/período

**Status:** 🟠 Parcial — oferta/versão/período/amostra operacionais

### Hoje

Existem métricas por oferta/versão com filtros inclusivos de período e amostra
mínima explícita.

### Falta

Filtros por:

```text
período
vertical
consultor
canal
provider
campaign
variant
offer_version
```

Exibir tamanho de amostra sempre.

---

## P1.26 — Precision@K operacional

**Status:** 🟠 Parcial

A função existe, mas precisa de uso real em BI/learning.

Medir:

```text
Precision@10(REPLIED)
Precision@10(MEETING)
Precision@25(WON)
```

com snapshot do ranking original.

---

## P1.27 — Niche Prior operacional

**Status:** 🟠 Parcial

Ligar learning a outcomes reais e OfferProfile.

Usar smoothing/amostra mínima.

Não ajustar ranking automaticamente com amostra pequena.

---

## P1.28 — Golden Lead Patterns operacionais

**Status:** 🟠 Parcial

Ligar `match_golden_patterns` ao pipeline/UI.

Patterns devem ficar associados a OfferProfile.

Exemplos:

### Landing Page

```text
NO_OWN_WEBSITE
+ HAS_INSTAGRAM
+ GOOD_REPUTATION
+ CONTACTABLE
```

### Engenharia

```text
INDUSTRIAL_CNAE
+ RELEVANT_OPERATION
+ INTENT_SIGNAL
+ DECISION_MAKER_REACHABLE
```

### Troféus

```text
EVENT_SCHEDULED
+ AWARDS_SIGNAL
+ CONTACT_WINDOW_GOOD
+ ORGANIZER_RESOLVED
```

---

## P1.29 — Learning controlado, sem autoedição prematura

**Status:** 🔵 Estrutural

Pipeline de aprendizado:

```text
observe
→ recommend
→ human approve
→ publish new OfferProfile version
```

### Não fazer ainda

LLM editar weights/thresholds automaticamente em produção.

### Requisitos futuros

- amostra mínima;
- intervalo de confiança;
- aprovação humana;
- versionamento;
- rollback;
- auditoria.

---

## P1.30 — A/B estatístico

**Status:** ✅ Operacional com aprovação auditável

Implementado:

- amostra mínima;
- confidence interval;
- comparação por versão da oferta;
- winner recommendation;
- indicação “dados insuficientes”;
- persistência em `commercial_comparisons`;
- endpoint e painel de BI;
- aprovação MANAGER/owner com auditoria.

---

# 11. P1 — Decision Maker e contatos

## P1.31 — Entidade canônica de pessoa

**Status:** 🟠 Parcial

### Problema

`PersonContact` existe como dataclass durante resolução, enquanto persistência continua espalhada entre `Contact`, snapshots e outras estruturas.

### Objetivo

Criar/evoluir uma entidade canônica mínima, sem construir um CRM completo.

Possível modelo:

```text
PersonIdentity
id
organization_id
company_record_id
normalized_name
display_name
role
buyer_type
email
phone
linkedin_url
identity_confidence
contact_confidence
verification_status
last_verified_at
sources
```

### Importante

Não reabrir automaticamente o antigo modelo completo `Company/Person/Employment` adiado. Resolver apenas a necessidade atual.

---

## P1.32 — Identity resolution não pode depender de CPF

**Status:** 🟠 Parcial

### Problema

No resolver atual, CPF tem peso estrutural muito forte para considerar pessoa “resolved”.

Isso funciona para QSA, mas não para gerentes B2B.

Exemplo confiável sem CPF:

```text
site oficial
+ LinkedIn atual
+ email corporativo
```

### Mudança

Calcular `identity_confidence` por evidências.

Exemplo inicial:

```text
CPF/QSA                  +50
site oficial             +35
email corporativo        +25
LinkedIn atual           +25
2 fontes concordantes    +20
```

Os pesos devem ser calibráveis.

### Resultado

`resolved` baseado em threshold de confiança, não em “tem CPF”.

---

## P1.33 — Source Reliability para contatos

**Status:** ⬜ Planejado

Nem todas as fontes têm a mesma qualidade.

Adicionar reliability por provider.

Exemplo inicial:

```text
receita_qsa         0.95
company_site        0.90
verified_email      0.90
linkedin_current    0.80
hunter              0.75
search_engine       0.55
heuristic           0.30
```

Usar no `ContactConfidence`.

---

## P1.34 — Pipeline real de People Discovery

**Status:** 🟠 Parcial

Completar:

```text
OfferProfile roles
→ company identity
→ people providers
→ identity merge
→ role matching
→ contacts
→ verification
→ buyer role
→ channel ranking
```

### Estado de saída obrigatório

```text
resolved
partial
not_found
failed
needs_review
```

Nunca transformar cargo configurado em pessoa encontrada.

---

## P1.35 — Domain-first person search efetivo

**Status:** 🟠 Parcial

A estratégia existe, mas precisa garantir provider real de pessoas.

Fluxo:

```text
normalized_domain
+ target titles
→ provider
→ candidates
→ dedup
→ identity resolver
```

Fallback:

```text
company name + city/state
```

---

## P1.36 — Contact cascade realmente orientada a custo/confiança

**Status:** 🟠 Parcial

Cascata recomendada:

```text
1. QSA/Receita
2. site oficial/equipe
3. people provider
4. email finder
5. LinkedIn assistido
6. telefone institucional roteável
7. pattern inference
8. verification
```

Early stopping deve usar:

```text
min_identity_confidence
min_contact_confidence
required_buyer_role
max_cost
max_steps
```

---

## P1.37 — Simplificar verificação async de contato

**Status:** 🟠 Parcial

### Problema

Há adaptações sync/async com threads dentro de resolução de identidade.

### Estado desejado

Separar:

```text
IdentityResolver = puro/síncrono
ContactVerifier = async/I/O
DecisionMakerPipeline = async orchestrator
```

Não abrir thread dentro do resolver para chamar verificação assíncrona.

---

## P1.38 — Remover scaffolding legado de contact providers quando seguro

**Status:** 🟠 Parcial

Ainda existem caminhos/retornos como:

```text
no_provider_active
queued_for_enrich_contacts
matched: []
```

em serviços antigos.

### O que fazer

- medir callers;
- migrar para pipeline novo;
- marcar deprecated;
- remover apenas após telemetria.

---

## P1.39 — Routable contact deve entrar de verdade na cadência

**Status:** 🟠 Parcial

Nome + departamento + telefone geral pode ser suficiente para ação humana.

A classificação agora é persistida em `Contact` (`routability_type`, `routable`
e `routability_reason`) e exposta na API. A integração da classificação com a
cadência continua pendente.

Cadência/next action deve distinguir:

```text
DIRECT
ROUTABLE
INSTITUTIONAL
UNREACHABLE
```

---

# 12. P1 — Engenharia Mecânica: qualidade comercial específica

## P1.40 — Semantic Enrichment industrial por oferta

**Status:** ⬜ Planejado

A arquitetura suporta Engenharia, mas ainda falta profundidade de sinais.

Criar extração orientada ao OfferProfile.

### Signals industriais

```text
HAS_CNC
OFFERS_USINAGEM
OFFERS_CALDEIRARIA
MANUFACTURES_CUSTOM_EQUIPMENT
HAS_PRODUCTION_LINE
HAS_ENGINEERING_DEPARTMENT
HAS_MAINTENANCE_TEAM
PRODUCT_DEVELOPMENT
CUSTOM_PARTS
REPLACEMENT_PARTS
AUTOMATION_OPERATION
TECHNICAL_DOCUMENTATION
NR12_MENTION
```

### Importância

Isso é mais útil para Engenharia do que SEO/SSL/tempo de carregamento.

---

## P1.41 — Projeto Mecânico

Melhorar profile com signals/intent específicos:

```text
NEW_EQUIPMENT
EXPANDING_FACTORY
NEW_PRODUCTION_LINE
CUSTOM_MACHINERY
AUTOMATION
HIRING_MECHANICAL_ENGINEER
HIRING_MAINTENANCE
```

---

## P1.42 — Desenho Técnico

Sinais:

```text
USINAGEM
CUSTOM_PARTS
REPLACEMENT_PARTS
REVERSE_ENGINEERING
CUSTOM_MANUFACTURING
CAD_NEED
```

Pergunta de validação:

> desenhos e detalhamentos são produzidos integralmente internamente ou usam parceiros externos?

---

## P1.43 — Manual de Máquinas / NR-12

Sinais:

```text
MACHINE_MANUFACTURER
NEW_MACHINE
INDUSTRIAL_SAFETY
NR12
TECHNICAL_DOCUMENTATION
CUSTOM_EQUIPMENT
```

Pergunta:

> como são produzidos e atualizados os manuais técnicos das máquinas entregues/operadas?

---

## P1.44 — Engenharia: case-study matching

**Status:** ⬜ Planejado

Associar cases do portfólio às oportunidades.

Exemplo:

```text
technical_drawing → case de detalhamento
mechanical_project → case de projeto/prototipagem
```

Objetivo: sugerir prova social correta na abordagem.

---

# 13. P2 — Administração de OfferProfiles

## P2.1 — CRUD/versionamento administrativo

**Status:** 🟠 Parcial

Somente depois de estabilizar schema.

Permitir:

```text
draft
validate
test
publish
deactivate
rollback
```

Tenant-scoped para profiles customizados.

Profiles globais protegidos.

---

## P2.2 — Tela de gestão de ofertas

Criar UI apenas após API/schema estarem estáveis.

---

# 14. P2 — Frontend e experiência operacional

## P2.3 — Contrato tipado de WebSocket

**Status:** 🟠 Parcial

Trocar mensagens livres por:

```json
{
  "schema_version": "1",
  "code": "DISCOVERY_PROVIDER_FAILED",
  "params": {},
  "severity": "warning"
}
```

Frontend traduz/copia.

---

## P2.4 — Catálogo de labels/textos

**Status:** 🟠 Parcial

Evitar enum/código cru:

```text
HOT
event_http
PROPOSTA_ENVIADA
```

aparecendo na UI.

---

## P2.5 — Estados de loading/error/empty para inteligência

Validar explicitamente:

- eventos;
- outcomes;
- oportunidades;
- decisores;
- providers.

---

## P2.6 — QA em celular/tablet real

**Status:** ⬜ Planejado

Validar:

- WebSocket;
- kanban;
- modais;
- drag-and-drop;
- foco;
- navegação;
- rede instável;
- touch.

---

# 15. P2 — Segurança e operação

## P2.7 — Fechar backlog de segurança individualmente

**Status:** 🟠 Parcial

Manter itens separados:

- Swagger em produção;
- CORS;
- upload limit;
- security headers;
- HTTPS/HSTS;
- webhook rate limit;
- redaction de e-mail;
- JWT `iss`/`aud`;
- reset token invalidation;
- inbound email isolation;
- login lockout;
- health endpoint;
- proteção de secrets.

Não usar um único checkbox “segurança concluída”.

---

## P2.8 — Custos e quotas

**Status:** ⬜ Planejado

Medir:

```text
Google calls
Groq tokens
Hunter credits
CNPJ calls
event provider calls
```

Gerar:

```text
cost_per_candidate
cost_per_lead
cost_per_qualified_lead
cost_per_actionable_contact
cost_per_meeting
cost_per_won
```

---

# 16. P2 — Métricas de decisão e bias

## P2.9 — Medir INSUFFICIENT_DATA

**Status:** ⬜ Planejado

Analisar:

```text
INSUFFICIENT_DATA
→ depois qualificou?
→ respondeu?
→ reunião?
→ vendeu?
```

Objetivo: calibrar required signals do pre-score.

---

## P2.10 — Exploration sampling

**Status:** ⬜ Planejado

Depois de volume suficiente, reservar pequena amostra de candidatos fora do top-K para detectar falsos negativos sistemáticos.

Nunca ativar sem:

- flag;
- amostra controlada;
- medição;
- limite de custo.

---

# 17. Itens conscientemente adiados

## 17.1 — Modelo completo Company/Person/Employment

**Status:** ⏸ Adiado

Não reabrir enquanto uma entidade mínima de pessoa resolver a necessidade atual.

## 17.2 — Drive/Sheets OAuth completo

**Status:** ⏸ Adiado

Reabrir apenas com escopo de produto específico.

---

# 18. Ordem recomendada de execução

## Onda 0 — confiabilidade

1. P0.5 observabilidade agregada por provider/custo/quota;
2. validação E2E externo com credenciais reais, quando houver ambiente de QA.

## Onda 1 — corrigir learning/outcomes antes de contaminar dados

1. P1.8 snapshot histórico da oportunidade;
2. P1.9 política de re-scoring;
3. P1.25 BI por vertical/consultor/canal/etapa/variante;
4. P1.26 Precision@K operacional;
5. P1.29 controlled learning após aprovação A/B.

## Onda 2 — contatos e decisores

1. P1.31 entidade canônica mínima;
2. P1.32 identity confidence sem CPF obrigatório;
3. P1.33 reliability por fonte;
4. P1.34 People Discovery real;
5. P1.36 cascade;
6. P1.37 async verification;
7. P1.39 routability.

## Onda 3 — Troféus / receita principal da AlphaMec

1. P1.17 evento → `trophies`;
2. P1.18 evento → decisor/ação;
3. P1.20 recorrência;
4. P1.21 janela ideal;
5. providers especializados MEJ/esportes além do endpoint HTTP genérico.

## Onda 4 — Engenharia excepcional

1. P1.11 job-intent real;
2. P1.12 semantic industrial signals;
3. P1.40 enrichment por oferta;
4. P1.41 projeto mecânico;
5. P1.42 desenho técnico;
6. P1.43 manual/NR-12;
7. P1.44 case-study matcher.

## Onda 5 — Learning/BI

1. P1.25 BI;
2. P1.27 niche prior;
3. P1.28 golden lead patterns;
4. P1.14 signal outcomes;
5. P1.30 A/B — manutenção e cortes adicionais;
6. P1.29 controlled learning.

## Onda 6 — administração/UX

1. OfferProfile admin;
2. WebSocket tipado;
3. catálogo de UI;
4. QA real;
5. remoção segura de legado.

---

# 19. Prioridade comercial específica para AlphaMec

Após fechar o P0, priorizar esforço de produto aproximadamente assim:

```text
40% — Troféus / Event Discovery
30% — Decision Maker / contatos reais
20% — Engenharia / intent e sinais industriais
10% — BI, UX e refinamentos gerais
```

Motivo: a arquitetura genérica já existe. O maior ganho agora vem de transformar dados em oportunidades vendáveis.

---

# 20. Definition of Done global

Uma pendência só pode virar **✅ Operacional** quando:

- [ ] há consumidor real;
- [ ] funciona no pipeline/UI;
- [ ] tenant scope é correto;
- [ ] erro/empty/unknown são distintos;
- [ ] há persistência quando necessária;
- [ ] há provenance;
- [ ] há versionamento quando afeta scoring/learning;
- [ ] unit tests existem;
- [ ] integration test existe;
- [ ] existe ao menos um cenário realista;
- [ ] observabilidade mínima existe;
- [ ] docs foram atualizados;
- [ ] não existe retorno placeholder sendo tratado como sucesso;
- [ ] o comportamento foi validado em PostgreSQL/ambiente equivalente;
- [ ] não contamina learning com fallback silencioso.

---

# 21. Checklist obrigatório por PR

- [ ] Li `docs/context.md`, `docs/architecture.md`, `docs/decisions.md` e este mapa.
- [ ] Confirmei callers reais antes de criar novo serviço.
- [ ] Evitei duplicar capability existente.
- [ ] Documentei tenant scope.
- [ ] Documentei erro vs vazio vs desconhecido.
- [ ] Adicionei testes.
- [ ] Adicionei migration quando necessário.
- [ ] Atualizei `docs/context.md`.
- [ ] Atualizei `docs/00-status-mapa.md`.
- [ ] Atualizei este arquivo.
- [ ] Rodei `python -m pytest tests -q`.
- [ ] Rodei `python -m compileall -q services/api services/workers`.
- [ ] Rodei lint/tsc/build Web quando frontend foi alterado.
- [ ] Validei que nenhum provider fake/placeholder está sendo reportado como sucesso.
- [ ] Registrei riscos/limitações reais no PR.

---

# 22. Estado-alvo

O sistema só estará maduro quando conseguir responder, com dados rastreáveis:

```text
1. Qual oferta faz sentido para esta organização?
2. Por que ela faz sentido?
3. Quais fatos sustentam isso?
4. O que é apenas hipótese?
5. Existe um gatilho agora?
6. Quem decide?
7. A pessoa encontrada é realmente quem pensamos?
8. Qual canal é acionável?
9. Qual pergunta valida a oportunidade?
10. Qual case deve ser usado?
11. Quanto custou encontrar essa oportunidade?
12. Esse tipo de oportunidade realmente converte?
```

Para Troféus:

```text
evento real
→ organizador
→ Lead
→ trophies opportunity
→ timing
→ decisor
→ ação
→ venda
→ recorrência
```

Para Engenharia:

```text
empresa industrial
→ atividade real
→ signals específicos
→ oferta correta
→ intent
→ decisor técnico/econômico
→ hipótese
→ pergunta de validação
→ reunião
→ outcome
```

O próximo estágio do projeto não é criar mais abstrações genéricas. É **fechar os fluxos que ligam descoberta, oportunidade, timing, decisor, ação comercial e aprendizado real**.
