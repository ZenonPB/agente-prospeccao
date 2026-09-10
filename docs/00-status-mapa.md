# Mapa de status operacional
> **Snapshot:** 2026-09-10 · branch `feat/oportunidade-historico-rescoring` ·
> Alembic head `3a5b7c9d1e2f`.
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
| OfferMatcher | ✅ | pós-scoring do enrichment | `lead_opportunities` + histórico append-only | sem tela administrativa dedicada |
| Oportunidades do lead | ✅ | `GET /api/leads/{id}/oportunidades` + `/historico` | score, evidências, versão, snapshots | resolução de oferta customizada em código |
| Event Discovery | ✅ opt-in | `source=events` no pipeline | `event_opportunities` | decisor/outreach ainda dependem de ação comercial humana |
| Provider HTTP de eventos | ✅ opt-in | `EVENT_DISCOVERY_URL` | status e provenance do evento | cobertura externa depende de endpoint configurado |
| Expiração de eventos | ✅ | scheduler da API | status `upcoming/expired` | recorrência e estados adicionais ainda não estão no escopo |
| Intent Engine | 🟠 | enrichment com HTML/jobs fornecidos | `lead.evidence_score.phase3` | falta job board/producer real |
| Decision Maker Resolution | 🟠 | `ContactEnrichmentService` + `PeopleProviderRegistry` opt-in + `HunterPeopleProvider` + `WebsitePeopleProvider` + ações de eventos | `contacts` + `persons` canônica + snapshots imutáveis + `next_best_action` + ação de evento persistida + role fit por título/senioridade/departamento | falta provider especializado adicional |
| Outcomes comerciais | ✅ | conversão/outcome service | `commercial_outcomes` | BI ainda não tem todos os cortes |
| Comparação A/B | ✅ | `/api/intelligence/comparisons` | `commercial_comparisons` + audit | aprovação exige recomendação conclusiva |
| Feedback humano de scoring | ✅ | rotas/UI de score feedback | `scoring_feedback`, `template_learning` | não é o mesmo que learning comercial |
| Learning/Metrics comercial | ✅ | outcomes + comparação + `/api/analytics/executive-metrics` | PostgreSQL + métricas derivadas org-scoped | controlled learning pendente |
| Observabilidade agregada | 🟠 | logs/jobs e status de providers | `provider_execution_metrics` + endpoint | faltam custo real e correlação consolidada com quota |
| OfferProfile administrativo | ⬜ | — | — | falta CRUD, publicação, versionamento e rollback |

## Capacidades históricas consolidadas

As 47 capacidades das ondas anteriores continuam cobertas pelo código e testes,
mas não são o backlog atual por si só. A matriz acima é a referência para as
capacidades que alteram a arquitetura e o fluxo comercial atual. O histórico
detalhado de propostas permanece em `docs/consolidacao.md` e
`docs/roadmap-vendas.md`, explicitamente como histórico/roadmap.

## Evidências de validação

- `python -m pytest tests -q -W error`: **1039 passed**.
- `python -m compileall -q services/api services/workers`: passou.
- Web: `npm run lint`, `npx tsc --noEmit` e `npm run build`: passaram.
- `scripts/verify_migrations.py`: head único `3a5b7c9d1e2f` (38 tabelas, 21 índices,
  24 FKs e 6 constraints únicas).
- Testes de persistência controlada usam PostgreSQL; o E2E externo continua
  opcional quando `E2E_DATABASE_URL` não está configurada.

## Próximas prioridades

1. P1.18/P1.35 — decisor → outreach automático: provider especializado
   adicional e integração futura de envio humano assistido.
2. Política explícita de re-scoring do score de oferta.
3. BI por vertical, consultor, canal, campanha, variante e controlled learning.
4. Entidade canônica de decisores e administração/versionamento de ofertas.