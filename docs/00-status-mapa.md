# Mapa de status operacional
> **Snapshot:** 2026-09-10 · branch `feat/controlled-learning-aprovacao` ·
> Alembic head `3d8e0f2a3b4c` (propostas de learning controlado pendentes de
> publicação manual; matcher ponderado `matcher-v2`, narrativa de oportunidade
> e golden patterns por oferta).
>
> Esta é a fonte de status por capacidade. “Completo” significa código no fluxo
> real, testes relevantes, escopo de organização e persistência quando
> necessária. A existência de um helper ou teste isolado não basta.

## Legenda

| Status | Significado |
|---|---|
| ✅ **COMPLETO** | Integrado ao fluxo real, testado e observável. |
| 🟠 **PARCIAL** | Há operação real, mas falta uma parte relevante do DoD. |
| 🔵 **ESTRUTURAL** | Contrato/helper existe, mas não há fluxo ponta a ponta. |
| ⬜ **PLANEJADO** | Ainda não existe implementação funcional relevante. |

## Capacidades principais

| Capacidade | Status | Entrada/consumidor | Persistência | Limitação atual |
|---|---|---|---|---|
| OfferProfile/Resolver | ✅ | `pipeline_worker` | contexto da campanha + versão | perfis cadastrados em código |
| Candidate pre-scoring | ✅ | pipeline antes do enrichment | `prescoring_discards` | calibração avançada ainda pendente |
| Discovery Places/CNAE | 🟠 | `DiscoveryExecutor` + adapters | leads/provenance consolidada + `prescoring_discards.provenance` | revisão fuzzy de merge ainda parcial |
| Enrichment adaptativo | ✅ | `enrichment_orchestrator` | `enrichments`/evidence | custo e cobertura dependem dos providers |
| Scoring vetorial contextual | ✅ | `AIScoringService` | campos/evidence do lead + snapshots de oportunidade | calibração avançada ainda pendente |
| OfferMatcher | ✅ | pós-scoring do enrichment | `lead_opportunities` + histórico append-only | ponderado por `signals.weights` (`matcher-v2` + `score_breakdown`); sem tela administrativa dedicada |
| Oportunidades do lead | ✅ | `GET /api/leads/{id}/oportunidades` + `/historico` | score, evidências, versão, snapshots | narrativa fato/hipótese/validação derivada na leitura; resolução de oferta customizada em código |
| Golden patterns | ✅ | matcher (evidence `golden:<id>`) | — (derivado de sinais observados) | lifts ainda heurísticos; calibração por outcomes pendente |
| Event Discovery | ✅ opt-in | `source=events` no pipeline | `event_opportunities` | decisor/outreach ainda dependem de ação comercial humana |
| Provider HTTP de eventos | ✅ opt-in | `EVENT_DISCOVERY_URL` | status e provenance do evento | cobertura externa depende de endpoint configurado |
| Expiração de eventos | ✅ | scheduler da API | status `upcoming/expired` | recorrência e estados adicionais ainda não estão no escopo |
| Intent Engine | 🟠 | enrichment com HTML/jobs fornecidos | `lead.evidence_score.phase3` | falta job board/producer real |
| Decision Maker Resolution | ✅ | `ContactEnrichmentService` + `PeopleProviderRegistry` opt-in + `HunterPeopleProvider` + `WebsitePeopleProvider` + `HttpPeopleProvider` federado + `BuyerPersona` + ações de eventos | `contacts` + `persons` canônica + snapshots imutáveis + `next_best_action` + ação de evento persistida + role fit por título/senioridade/departamento + gates de identidade/buyer role | outreach automático segue humano assistido |
| Outcomes comerciais | ✅ | conversão/outcome service + `GET /api/analytics/outcomes-breakdown` | `commercial_outcomes` | cortes por vertical/consultor/campanha/provider/versão prontos; canal/variante/etapa sem coluna |
| Comparação A/B | ✅ | `/api/intelligence/comparisons` | `commercial_comparisons` + audit | aprovação exige recomendação conclusiva |
| Feedback humano de scoring | ✅ | rotas/UI de score feedback | `scoring_feedback`, `template_learning` | não é o mesmo que learning comercial |
| Learning/Metrics comercial | 🟠 | outcomes + comparação + propostas + `/api/analytics/executive-metrics` | PostgreSQL + métricas derivadas org-scoped | publicação e aplicação controladas pendentes |
| Observabilidade agregada | 🟠 | logs/jobs e status de providers | `provider_execution_metrics` + endpoint | faltam custo real e correlação consolidada com quota |
| OfferProfile administrativo | ⬜ | — | — | falta CRUD, publicação, versionamento e rollback |

## Capacidades históricas consolidadas

As 47 capacidades das ondas anteriores continuam cobertas pelo código e testes,
mas não são o backlog atual por si só. A matriz acima é a referência para as
capacidades que alteram a arquitetura e o fluxo comercial atual. O histórico
detalhado de propostas permanece em `docs/consolidacao.md` e
`docs/roadmap-vendas.md`, explicitamente como histórico/roadmap.

## Evidências de validação

- `python -m pytest tests -q -W error`: **1097 passed, 19 skipped**.
- `python -m compileall -q services/api services/workers`: passou.
- Web: `npm run lint`, `npx tsc --noEmit` e `npm run build`: passaram.
- `scripts/verify_migrations.py`: head único `3d8e0f2a3b4c`, incluindo a tabela
  de propostas controladas e o breakdown persistido do matcher.
- Testes de persistência controlada usam PostgreSQL; o E2E externo continua
  opcional quando `E2E_DATABASE_URL` não está configurada.

## Fontes de verdade (declaradas na Onda 0A)

| Assunto | Fonte canônica |
|---|---|
| Status por capacidade (o que está ✅/🟠/🔵/⬜) | este mapa (`00-status-mapa.md`) |
| Backlog operacional (o que falta fazer) | `pendencias-pos-consolidacao.md` |
| Arquitetura e fluxos reais | `architecture.md` |
| Histórico e planos de longo prazo | `consolidacao.md`, `roadmap.md`, `roadmap-vendas.md` |
| Estado vivo + próximo passo | `context.md` |

Em caso de conflito, vale o código + testes; o documento divergente é corrigido,
nunca o contrário.

## Reconciliação Onda 0A (verdade documental)

- **P1.32 (identity confidence sem CPF): ✅ Operacional.** Cálculo por evidências
  sem exigir CPF, com `resolved >= 70`, persistido e consumido pelo waterfall;
  prova em `tests/test_decision_maker_resolution.py:79-100,191-217`. Resta tornar
  os pesos calibráveis via configuração (Onda 1).
- **P1.33 (Source Reliability): ✅ Operacional no cálculo e na persistência.**
  Registry com os valores do plano, integrado ao `contact_confidence`, persistido
  e exposto na API/UI; prova em `tests/test_decision_maker_resolution.py:182-189`.
  Uso em gates de decisão e no Intent v2 continua ⬜ Planejado.
- **Drifts código-vs-docs registrados** (detalhes em
  `pendencias-pos-consolidacao.md` §23, não corrigidos nesta entrega):
  F-01 `formula_version` (`matcher-v2` em runtime vs `matcher-v1` no
  schema/docs); F-02 unique `uq_controlled_learning_org_offer_version` ausente no
  modelo; F-03 `POST /campaigns/from-brief` resolve template, nunca perfil;
  F-04 conflito sobre re-scoring entre este mapa e as pendências (P1.9 é
  ✅ Operacional — este item de "Próximas prioridades" será removido na próxima
  varredura).

## Próximas prioridades

1. P1.18 — decisor → outreach humano assistido: envio com aprovação humana
   sobre a base federada (providers, filtros, snapshots e timing prontos).
2. Política explícita de re-scoring do score de oferta.
3. BI por vertical, consultor, canal, campanha, variante e controlled learning.
4. Entidade canônica de decisores e administração/versionamento de ofertas.