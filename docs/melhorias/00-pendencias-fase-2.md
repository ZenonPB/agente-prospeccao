# Pendências e polish da Fase 2 — antes da próxima fase

> **Snapshot: 2026-09-04**, branch `feat/fase2-sinais-e-episteme`.
> A Fase 2 (sinais, enrichment, score vetorial, status epistêmico) está **fechada
> e validada** (4 ondas, 618 testes, 2 migrations no Postgres real). Este
> documento lista **o que ainda precisa ser ajustado/polish/fechado** dentro
> dessa mesma fase — ou seja, o que **NÃO** está alinhado com a spec dos 12 docs
> `-FEITO.md` ou tem buracos pequenos que ficaram para trás na revisão.

## Legenda

| Marca | Significado |
|---|---|
| 🐞 **bug** | Comportamento divergente do contrato do doc. |
| 🧹 **polish** | Refino de UX/API, sem mudar contrato. |
| 📈 **observabilidade** | Métrica/contador que deveria existir e não existe. |
| 🧪 **cobertura** | Caso de teste ausente. |
| 📚 **doc** | Documentação divergente do código. |

## 1. `VECTOR_WEIGHTS` incompleto para perfis `industrial` e `landing_pages`

**🐞 + 🧹** · `services/workers/src/services/scoring_service.py:279`

O dict `VECTOR_WEIGHTS` declara pesos específicos apenas para `web_presence`,
`business_opportunity` e `generic` (fallback). Os perfis `industrial` (usado
pelo template "Engenharia Mecânica") e `landing_pages` (Landing Pages) caem
no `generic` por `.get(profile, VECTOR_WEIGHTS["generic"])`.

Impacto: o `overall` do `score_vector` para esses perfis é a média simples
das 4 dimensões — perde a ênfase de que **industrial valoriza `need`/`commercial_fit`**
e **landing_pages valoriza `digital_maturity`** (a conversão é o que importa).

Ação:
- Adicionar entradas `"industrial"` e `"landing_pages"` em `VECTOR_WEIGHTS`
  com pesos coerentes com a config do template (e com os pesos de pre-score
  já existentes no `prospecting_profile_service.DEFAULT_PRESCORING_WEIGHTS`).
- Atualizar `tests/test_score_vector_dims.py` com asserções para os dois novos
  perfis.

## 2. Endpoint e painel de leitura dos `prescoring_discards`

**📈 + 🧹** · `services/workers/src/database/models.py:984`
`PrescoringDiscard` é populado (idempotente por `campaign_id`+`place_id`),
mas **não há rota de leitura** nem UI para auditoria de falsos-negativos /
recalibração de thresholds (docs 01/12).

Ação:
- API: `GET /api/campaigns/{id}/prescoring-discards` (org-scoped,
  filtros: `reason`, `profile_key`, `min_score`, `from`/`to`).
- Web: nova seção "Descartes do pre-scoring" em `/campanhas/[id]` (card
  resumo + tabela paginada com `company_name`, `discovery_score`,
  `threshold`, `reason`, `signals[]`, `profile_key`, `created_at`).

## 3. Migração das regexes de vertical para configuração

**📚 + 🧹** · `services/workers/src/services/scoring_service.py:55-95`

`_WEB_PRESENCE_LABELS`, `_SELLS_WEB_PRESENCE`, `_ERP_WEBAPP_LABELS` e
`_campaign_sells_erp_webapps` continuam hardcoded no `scoring_service.py`
(ADR: "ficam como fallback legado até revalidação dos fixes de falso-positivo
ERP"). Os fixes de C5 (2026-08-14) e o template "Aplicações Web / ERP" ampliado
seguem estáveis, então essa migração pode acontecer sem revalidação longa.

Ação:
- Mover os labels/regexes para config no template
  (`campaign_scoring_templates.web_presence_labels`,
  `campaign_scoring_templates.erp_webapp_labels`) ou para uma constante
  no `prospecting_profile_service` (fonte única do engine).
- O scoring lê dessas configs em vez do módulo — engine fica 100% genérico
  em relação à vertical.

## 4. `_serialize` do template — outros campos opcionais ainda não cobrem?

**📚** · Investigar `services/workers/src/services/scoring_templates.py`
e o `_serialize` que já foi corrigido para incluir `prescoring_config`
(ADR no `decisions.md`). Verificar se a serialização inclui:


## 5. `required_signals` / `on_insufficient_data` ainda não exercitados pelos seeds

**🧪** · `services/workers/src/services/prospecting_profile_service.py:167`

O schema do `prescoring_config` aceita `required_signals` (lista de chaves
de `SignalKey` que precisam ter sido observadas) e `on_insufficient_data`
(`discard`/`promote`), com 5 testes em `test_gate_required_signals.py`. Mas
**nenhum seed** declara esses campos:

- Templates de Engenharia gostariam de `required_signals: [CNAE]` (o sinal
  decisivo é pós-gate, mas o CNAE do **Google Places category** pode
  aproximar — quando a categoria do Places já é industrial, é seguro
  promover; quando não, deixar o enrichment cadastral decidir).
- O default `discard` atual significa que **todos os seeds estão descartando
  sem o opt-in consciente**. Confirmar com a EJ qual deve ser o
  `on_insufficient_data` por template e aplicar via seed.

Ação:
- Definir `required_signals` + `on_insufficient_data` por seed de template
  (decisão de produto, não de código).
- Atualizar o seed e validar com smoke E2E.

## 6. `prescoring_discarded` (int) + `prescoring_breakdown` (dict) no summary

**🧹** · `services/api/src/pipeline_worker.py:919,938`

O summary do job retorna ambos para retrocompatibilidade, mas o `int` é
agora derivado de `sum(breakdown.values())` — o consumidor (UI/WS) pode
migrar para o dict e ganhar granularidade (`below_threshold` vs `top_k_cut`
vs `insufficient_data`). Não é bug, é oportunidade de limpar o contrato
em uma próxima major.

## 7. `why_signals` sem distinção por severidade/peso

**🧹 + 🧪** · `services/api/src/routes/leads.py:170`

Hoje: `[(e.get("title")) for e in (lead.evidence or [])[:3]]` — pega os
3 primeiros títulos de evidence, sem considerar a `severity` do evidence
(`high`/`medium`/`low`) nem o `weight` dos `score_factors`. Se o scoring
devolve 10 evidences com a primeira sendo "baixa" (`severity: low`), o
card mostra os 3 piores.

Ação:
- Ordenar por `severity` desc (`high` > `medium` > `low`) e, dentro, pela
  ordem original; ou usar o ranking dos `score_factors` (positivos primeiro,
  depois negativos, ambos com `impact` desc).
- Atualizar o teste em `test_score_vector_dims.py:94` para cobrir a
  ordenação por severidade.

## 8. `discovery_status` (QUALIFIES/INSUFFICIENT_DATA/DISQUALIFIES) sem superfície de UI

**🧹** · `services/workers/src/services/candidate_pre_scoring_service.py:165`

O gate devolve o novo `discovery_status` no scoring do candidato (e os
stats do job incluem `insufficient_data`/`insufficient_data_promoted`), mas
**a UI ainda não distingue**:

- "Descartado por falta de dados" (INSUFFICIENT_DATA) deveria ser visível
  no relatório de descartes (item 2).
- "Descartado por threshold" (DISQUALIFIES) é o que o consultor quer ver
  como "falso-negativo a calibrar".

Ação:
- Incluir `discovery_status` em `_lead_summary` e na tabela de descartes
  do painel (item 2).
- Colorir/etiquetar cada linha com o motivo (`INSUFFICIENT_DATA` é diferente
  de `below_threshold`).

## 9. Cobertura de testes — alguns cenários da Fase 2 ainda não estão

**🧪**

Verificar/expandir:

- `discovery_multi_query.py`: dedup por `name+categoria` quando `place_id`
  é None — testar com 2 candidatos que diferem só em acento/caixa.
- `enrichment_capability_registry.plan_enrichment_run` com
  `enrichment_strategy.skip` E `stop_after` no MESMO template.
- `signal_registry.merge_signals` com providers que divergem no
  `observed_at` em formato diferente (ISO vs Z vs sem TZ).
- `candidate_pre_scoring_service.select_candidates` com
  `on_insufficient_data="promote"` + `top_k` aplicado — comportamento
  cruzado.
- `scoring_service._normalize_response` quando o LLM devolve `score_vector`
  com dimensões **fora** do `VECTOR_WEIGHTS` daquele perfil (ex.: envia
  `icp_fit`, mas o perfil só conhece 4 dimensões). O código atual cai no
  else `sum(clean_vector.values()) / len(clean_vector)` — coerente? ou
  deveria descartar as dimensões extras?

## 10. Observabilidade — métricas dos sinais no job

**📈**

O job hoje loga o `prescoring_stats` e o summary de descartes. Falta:

- Contador de sinais **promovidos** vs **descartados** por chave
  (`NO_OWN_WEBSITE`, `HAS_INSTAGRAM`, `CNAE`...) — alimenta calibração de
  pesos.
- Contador de **INSUFFICIENT_DATA por chave ausente** (`CNAE` faltou em
  X candidatos industriais) — sinal claro de onde os seeds precisam de
  decisão de produto.

---

## Resumo executivo das pendências

| # | Tipo | Item | Esforço | Bloqueia Fase 3? |
|---|---|---|---|---|
| 1 | 🐞 | `VECTOR_WEIGHTS` sem perfis `industrial`/`landing_pages` | XS | Não (consistência) |
| 2 | 📈 | Endpoint/painel de `prescoring_discards` | M | Não |
| 3 | 📚 | Migrar regexes de vertical para config | M | Sim (engine 100% genérico) |
| 4 | 📚 | Auditar `_serialize` do template | XS | Não |
| 5 | 🧪 | Aplicar `required_signals`/`on_insufficient_data` nos seeds | S | Não |
| 6 | 🧹 | Limpar `prescoring_discarded` (int vs breakdown) | XS | Não |
| 7 | 🧹 | `why_signals` ordenar por `severity` | XS | Não |
| 8 | 🧹 | UI expor `discovery_status` (INSUFFICIENT_DATA) | S | Não |
| 9 | 🧪 | Cobertura de testes (5 cenários) | S | Não |
| 10 | 📈 | Métricas de sinais no job | M | Não |
| 11 | 📚 | Sincronizar `decisions.md`/`context.md` | XS | Não |
| 12 | 🧹 | UX mobile do card (3 chips) | XS | Não |
| 13 | 📚 | Migração da métrica IA × Time para `score_vector` | M | Não |

**Bloqueador único para Fase 3 (#22 Discovery Planner):** item 3 (regexes
fora do core). O resto é polish paralelo.

## O que **NÃO** é pendência da Fase 2

- **Pendências de Fase 0/1 (anteriores):** nada aberto — o
  `00-diagnostico-fase-1.md` lista 5 itens "NÃO foi implementado" e os 5
  estão hoje cobertos (descartes auditados, ordem condicional, capability
  registry, dimensões do vetor, ProspectingProfile).
- **Pendências do roadmap comercial:** 4.20 (Drive/Sheets OAuth) e 4.27
  (modelo 3 entidades) seguem **adiados por ADR** — não bloqueiam o
  pacote de melhorias.
- **Pendências de produto:** o que é opt-in (WhatsApp na cadência,
  campanhas por linguagem natural com multi-query automática) é decisão
  da EJ, não da engenharia.

- Endpoint `GET /api/campaigns/{id}/prescoring-stats` com histograma por
  `profile_key` × `reason`.

## 11. Migration review — pendências de housekeeping

**📚**

- `decisions.md` ainda referencia a Fase 2 como "em progresso" em algumas
  linhas (verificar linha-a-linha) — alinhar com o status real "✅ Pronta".
- `context.md` §"Fase 2" lista o que foi entregue mas pode estar sem o
  registro explícito do `prescoring_breakdown` como stats — adicionar
  parágrafo curto.

## 12. UX do card de leads — `why_signals` saturado

**🧹**

Card mostra 3 chips curtos. Em telas estreitas (mobile, kanban) podem
estourar. Já existe `WhyProspectSignals` em
`apps/web/src/components/oportunidades/lead-list.tsx:526` — verificar
se tem fallback (truncar com reticências) e se respeita o `severity` do
evidence (não mostra "Avaliação 4.5★" antes de "Sem CTA").

## 13. Convergência IA × Time ainda não consome o `score_vector`

**📚 + 🧹**

A métrica `|score IA − score consultor|` existe
(`GET /api/leads/score-feedback-metrics`) mas usa o `qualification_score`
legado. Quando migrarmos o funil para o `score_vector.overall` (futuro),
o card "Convergência IA × Time" em `/relatorios` precisa apontar para o
overall novo (e por dimensão, idealmente). Não é urgente — `qualification_score`
segue como fonte de verdade — mas registrar como débito.

- `cadence_schedule` (templates com `[0, 7, 30, 60]` precisam chegar ao
  orquestrador de cadência sem perda).
- `playbook` (consultas do LinkedIn, hooks, subject_ideas, objections).
- `enrichment_strategy` (skip / stop_after).
- `vector_weights` (se quisermos pesos POR TEMPLATE, sobrepondo o default).

Se algum desses não estiver no `_serialize`, leads que dependem deles
silenciosamente caem no default — bug latente.
