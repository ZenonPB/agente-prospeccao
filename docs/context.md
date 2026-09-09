# Prospect.ai — Contexto vivo

> Leia este arquivo primeiro. Ele contém o estado atual; o histórico detalhado
> está em `docs/consolidacao.md` e `docs/roadmap-vendas.md`.
>
> **Snapshot:** 2026-09-09 · branch `feat/onda-avanco-maximo` ·
> Alembic head `2b4d6f8a0c2e` (Person canônica + provenance de descarte).
>
> **Nota de ambiente:** o banco local desta máquina está em `c9d0e1f2a3b4`
> (pendente de `alembic upgrade head`); rode
> `python scripts/verify_migrations.py --upgrade --database-url <URL>` em
> ambiente com Postgres antes de validar E2E.

## Leitura obrigatória

1. `docs/architecture.md` — arquitetura e fluxos reais;
2. `docs/business-rules.md` — funil, scoring, cadência e limites;
3. `docs/00-status-mapa.md` — status por capacidade;
4. `docs/pendencias-pos-consolidacao.md` — backlog operacional;
5. `docs/decisions.md` e `docs/coding-standards.md` — decisões e padrões.

## Estado atual

O produto opera como plataforma multi-tenant em Web Next.js, API FastAPI,
workers Python async e PostgreSQL. O pipeline de empresas é orientado por
`OfferProfile` quando configurado, usa `DiscoveryExecutor` para Places/CNAE,
enrichment passivo, scoring contextual, `OfferMatcher`, decisores best-effort e
outreach/cadência. Campanhas legadas continuam compatíveis.

### Capacidades entregues nesta consolidação (onda 2 — fechamento de fluxos)

- **Verificação de contato sem rede oculta (P1.37)**: o bloco com thread e o
  hack de `sys.modules` foram removidos do `ContactVerification` legado em
  `decision_maker_resolution.py`; a verificação real de e-mail é
  responsabilidade exclusiva do seam async `ContactVerifier`, executada pelo
  orquestrador, e o teste de integração cobre a ausência de rede oculta.
- **Early stopping por orçamento no waterfall (P1.36)**:
  `PeopleProviderRegistry.waterfall_search` aceita `max_cost`; providers fora
  do orçamento restante ficam com status `budget_exceeded` (nunca consultados)
  e o resultado reporta `cost_spent`, cobrado apenas em chamadas com
  resposta. O evidence `people_discovery` do lead persiste o custo gasto.
- **Roteabilidade na próxima ação (P1.39)**: `NextBestActionService`
  distingue `DIRECT_CONTACT`/`ROUTABLE_CONTACT` (CALL),
  `INSTITUTIONAL` (RESEARCH via recepção) e `UNKNOWN`/`UNREACHABLE`
  (RE_ENRICH); a API repassa `routability_type` do contato e
  `prepare_event_actions` usa o mesmo critério.
- **Provenance no descarte do pre-scoring (P1.2)**: coluna `provenance` em
  `prescoring_discards` (migration `2b4d6f8a0c2e`) com providers, consultas e
  ids do candidato rejeitado; upsert e endpoint de auditoria expõem o campo.
- **Ação de evento persistida (P1.18)**: `prepare_event_actions` grava
  `decision_maker_id`/`decision_maker_status`, canal recomendado,
  `action_status` e `next_action` no row do evento, expostos em
  `/api/intelligence` e na UI de relatórios.

### Capacidades entregues nesta consolidação (onda 0 — confiabilidade)

- **Identidade cross-provider de empresas**: tabela `company_aliases`
  registra chaves externas (place_id, domínio, maps_uri, id sintético
  CNAE/PNCP) por Company; `CompanyPersonService` resolve por CNPJ → domínio →
  aliases e faz backfill de campos vazios. O pipeline (Places, CNAE e PNCP)
  consulta a Company antes de criar Lead, mesclando provenance e aliases em vez
  de duplicar. Merge fuzzy (nome+cidade/UF) continua apenas candidato.
- **Observabilidade de providers completa**: `provider_execution_metrics`
  persiste `correlation_id`, `campaign_id` e `usage` (tokens Groq em JSONB),
  preenchendo também `cost` (estimativa USD por modelo). Discovery
  (Places/CNAE), Event Discovery e scoring emitem métricas por execução.
- **Correlation IDs**: cada `run_pipeline` gera um UUID logado na abertura do
  job, propagado a toda telemetria e devolvido no payload final do
  WebSocket/job com `provider_metrics` agregadas.
- **Telemetria de tokens Groq**: `groq_json_chat` ganhou callback `on_usage`
  (sem mudar o retorno dos chamadores); o `AIScoringService` repassa o
  callback e o pipeline acumula tokens + custo estimado por lote.
- **Endpoint `GET /analytics/provider-trace/{correlation_id}`** (org-scoped):
  devolve todas as medições de uma execução (status, latência, erro, custo,
  tokens) — responde "por que esta campanha trouxe poucos leads".
- Nova migration `1a2b3c4d5e6f` (head): `persons` canônica com
  identidade/contato/verificação e acionabilidade, propagada de `Contact` via
  `CompanyPersonService.sync_lead_entities`, sobre a base `ff8a9b0c1d2e`
  (`company_aliases` + Onda 0).

### Legado da consolidação anterior (preservado)

- `lead_opportunities` persiste múltiplas oportunidades por lead, oferta,
  versão e evidências; o endpoint é org-scoped.
- `source=events` executa Event Discovery como job separado, com provider HTTP
  opt-in (`EVENT_DISCOVERY_URL`), retry, Bearer opcional, estados `ok`, `empty`,
  `failed` e `skipped`, deduplicação, provenance, OrganizerResolver e vínculo
  seguro com `Company`/`Lead`. Eventos futuros vinculados a um lead também geram
  de forma idempotente uma oportunidade `trophies` via `OfferMatcher`; decisor e
  outreach continuam no loop humano.
- `event_opportunities` preserva histórico e o scheduler marca eventos vencidos
  como `expired` de forma idempotente. Timestamps ISO recebidos como string são
  normalizados para UTC antes da persistência.
- `commercial_outcomes` e `commercial_comparisons` fornecem o caminho persistido
  de métricas e comparação A/B com Wilson, amostra mínima, aprovação humana e
  auditoria. `learning_metrics.py` é o adaptador in-memory usado por esse
  serviço e pelos testes, não a persistência principal.
- Conversões preservam oferta/versão/oportunidade, com fallback `unknown`
  revisável.
- Execuções de providers registram métricas estruturadas no resumo do job
  (`status`, quantidade, duração, erro e retryability) e em
  `provider_execution_metrics`, com `correlation_id`, `campaign_id`, `usage`
  (tokens) e `cost` (estimativa USD); a quota continua sendo medida
  separadamente em `provider_usage`.
- Contatos persistem `identity_confidence`, `contact_confidence`, confiabilidade
  da fonte, status de verificação e classificação de acionabilidade (`DIRECT`,
  `ROUTABLE`, `INSTITUTIONAL` ou `UNKNOWN`).
- `DecisionMakerResolver` distingue `resolved/partial/needs_review/not_found/failed`:
  identidade ambígua sem CPF (mesmo nome, e-mails distintos, confiança < 70)
  retorna `needs_review` em vez de `partial` silencioso; `failed` indica
  exceção de provider (retryable), nunca ausência de pessoa.
- `ContactVerifier` async separado do resolver sync: verificação de e-mail por
  serviço injetado, sem thread nem DNS oculto no resolver.
- `Person` canônica carrega identidade/contato/verificação/acionabilidade
  (migration `1a2b3c4d5e6f`); `CompanyPersonService` propaga os campos de
  `Contact` no `sync_lead_entities` sem sobrescrever dado existente.
- `ContactEnrichmentService` aceita o seam de verificação com/sem mock
  explícito (`_accepts_mock_check`), sem mudar o fluxo de `evidence_score`.
- `PeopleProviderRegistry` define o seam assíncrono de waterfall de pessoas,
  com deduplicação, early stopping e estados explícitos, mas permanece sem
  provider externo habilitado por padrão. `HunterPeopleProvider` é o primeiro
  adapter real; só é registrado quando a organização tem `HUNTER_API_KEY` e
  uma quota positiva explícita em `api_quota`.
- `NextBestActionService` recomenda uma ação explicável sem efeitos colaterais
  e a API a expõe em `GET /api/leads/{id}` como `next_best_action`; o envio
  continua humano no loop.
- Candidatos de discovery carregam provenance consolidada no `Lead`, incluindo
  providers, consultas, identificadores externos, plano e regra de identidade;
  merges automáticos ocorrem apenas por chaves fortes.

### Validação do snapshot

- `python -m pytest tests -q -W error`: **1001 passed** (unit; testes com
  Postgres real rodam apenas com `E2E_DATABASE_URL`/banco ativo);
- `python -m compileall -q services/api services/workers`: passou;
- Web: lint, TypeScript e build: passaram;
- `scripts/verify_migrations.py`: head único `2b4d6f8a0c2e`;
- persistência controlada validada em PostgreSQL.

## Próximo passo imediato

Waterfall multi-provider de pessoas (P1.34/35): registrar um segundo provider
real além do Hunter (opt-in por organização) e aplicar role fit do
OfferProfile no early stopping, mantendo quota, telemetria e orçamento. As
demais prioridades estão em `docs/pendencias-pos-consolidacao.md`.