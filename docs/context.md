# Prospect.ai — Contexto vivo

> Leia este arquivo primeiro. Ele contém o estado atual; o histórico detalhado
> está em `docs/consolidacao.md` e `docs/roadmap-vendas.md`.
>
> **Snapshot:** 2026-09-10 · branch `feat/controlled-learning-aprovacao` ·
> Alembic head `4a6b8c9d1e2f` (propostas de learning controlado pendentes de
> publicação manual; matcher ponderado `matcher-v2`, narrativa de oportunidade
> e golden patterns por oferta).
>
> **Nota de banco (onda 3 — auditoria):** o banco local foi resetado
> (drop/recreate do schema) e reconstruído com `alembic upgrade head`;
> backup prévio conservado em `backups/` (gitignored). Motivo: o banco
> estava na revisão `c9d0e1f2a3b4`, que não existe mais no repositório
> (carregava a tabela órfã `identity_reviews` de uma linha abandonada).

## Leitura obrigatória

1. `docs/architecture.md` — arquitetura e fluxos reais;
2. `docs/business-rules.md` — funil, scoring, cadência e limites;
3. `docs/00-status-mapa.md` — status por capacidade;
4. `docs/pendencias-pos-consolidacao.md` — backlog operacional;
5. `docs/decisions.md` e `docs/coding-standards.md` — decisões e padrões.

## Fontes de verdade (declaradas na Onda 0A)

| Assunto | Fonte canônica |
|---|---|
| Status por capacidade | `docs/00-status-mapa.md` |
| Backlog operacional | `docs/pendencias-pos-consolidacao.md` |
| Arquitetura e fluxos reais | `docs/architecture.md` |
| Histórico e planos de longo prazo | `docs/consolidacao.md`, `docs/roadmap.md`, `docs/roadmap-vendas.md` |
| Estado vivo + próximo passo | este arquivo (`docs/context.md`) |

Em caso de conflito, vale o código + testes; o documento divergente é corrigido,
nunca o contrário.

## Reconciliação Onda 0A (verdade documental)

- **P1.32 (identity confidence sem CPF) e P1.33 (Source Reliability): ✅
  Operacionais** no cálculo, persistência e fluxo real (pesos ainda literais no
  código; torná-los calibráveis via configuração é escopo da Onda 1). Uso de
  reliability em gates/Intent v2 continua planejado. Provas e detalhes em
  `docs/00-status-mapa.md` e `docs/pendencias-pos-consolidacao.md` (§P1.32/P1.33).
- **Drifts F-01, F-03 e F-04 corrigidos na Fatia 1** (`pendencias-pos-consolidacao.md`
  §23): default `matcher-v2` alinhado (migration `4a6b8c9d1e2f`), from-brief sugere
  `offer_profile_key`, item de re-scoring removido do mapa. Resta F-02 (unique
  ausente no modelo — sem efeito operacional).

## Estado atual

O produto opera como plataforma multi-tenant em Web Next.js, API FastAPI,
workers Python async e PostgreSQL. O pipeline de empresas é orientado por
`OfferProfile` quando configurado, usa `DiscoveryExecutor` para Places/CNAE,
enrichment passivo, scoring contextual, `OfferMatcher`, decisores best-effort e
outreach/cadência. Campanhas legadas continuam compatíveis.

### Capacidades entregues nesta consolidação (onda 4 — oportunidade explicável)

- **Matcher ponderado por oferta (P1.7 ✅)**: fórmula `matcher-v2` pondera
  sinais por `signals.weights` (`matched_weight/total_weight × 70`, peso
  ausente = 1; sem pesos, igualitário legado bit a bit). As três ofertas
  industriais declaram os mesmos positivos com pesos diferentes (formalidade
  × contato direto × visita técnica). `score_breakdown` expõe signal/icp,
  pesos e motivo de desqualificação; validador P1.4 estendido para
  `signals.weights`.
- **Narrativa "why this offer" (P1.10 ✅)**: `build_opportunity_narrative`
  separa FATOS, HIPÓTESE e VALIDAÇÃO, derivada na leitura (sem coluna nova,
  histórico nunca reescrito) e exposta como `narrative` em
  `GET /api/leads/{id}/oportunidades`.
- **Golden patterns por oferta (P1.28 ✅)**: cinco padrões (landing_page,
  mechanical_project, technical_drawing, machine_manual, trophies) +
  fallback por arquétipo + legados preservados; wiring no matcher
  (`golden:<id>` só de sinais observados, parcial nunca reportado).

### Capacidades entregues nesta consolidação (onda 3 — People Discovery)

- **Fonte especializada federada opt-in (P1.35 ✅)**: `HttpPeopleProvider`
  pluga qualquer fonte especializada (Apollo/Clay/Snov/base interna) via
  endpoint JSON próprio (`PEOPLE_DISCOVERY_URL` + Bearer opcional), com retry
  de transitórios, distinção `failed`/`empty`/`disabled`/`quota_exceeded`/
  `invalid_request`/`configuration_error`, rejeição de domínio inválido e
  proteção SSRF, provenance e `email_verified` nunca inventado. Opt-in duplo
  fail-closed (endpoint global + quota `PEOPLE_DISCOVERY_HTTP` da org);
  registrado entre site (0.25) e Hunter (1) por custo (0.5).
- **Gates de buyer no waterfall (P1.36 ✅)**: `waterfall_search` exige
  `min_identity_confidence` e `required_buyer_role` para early stopping
  (buyer role explícito prevalece; sem ele, inferência determinística;
  `UNKNOWN` nunca finge match; `buyer_role_not_matched` distinto de
  `role_not_matched`). `discovery_limits` lê os gates do `people_discovery`
  e usa `decision_makers.buyer_types` como fallback; evidência e `raw_data`
  persistem buyer role, fonte, status e identidade.
- **Entidade `BuyerPersona`**: 8 personas iniciais (founder, marketing,
  operations, engineering, maintenance, safety, event director, procurement)
  com title patterns, senioridade, departamento, buyer type, prioridade e
  canais; `match_persona_for_role` e validação semântica das novas chaves
  no build do registry (P1.4 estendido).

- **People Discovery multi-provider opt-in**: `WebsitePeopleProvider` consulta
  somente páginas públicas conhecidas do domínio oficial e extrai JSON-LD
  `Person`; limita tamanho de HTML, rejeita redirecionamentos externos e IPs
  privados, usa quota própria (`WEBSITE_PEOPLE_PROVIDER`) e nunca é habilitado
  sem opt-in explícito da organização.
- **Role fit configurável**: `PeopleProviderRegistry` anota
  `role_fit_score`, `role_fit_status`, `matched_titles`, senioridade,
  departamento e outcome dos filtros; preserva o melhor fit na deduplicação e
  aceita `min_role_fit` para early stopping. O resultado distingue
  `role_not_matched` de ausência/falha do provider.
- **OfferProfile no waterfall**: perfis padrão declaram limites de People
  Discovery (`max_cost`, `max_steps`, `min_role_fit`, senioridade,
  departamento, `min_identity_confidence`, `required_buyer_role` com fallback
  para `decision_makers.buyer_types`); o enriquecedor resolve o
  perfil efetivo da campanha, passa esses limites ao registry e persiste
  `role_fit`, `buyer_role`, tentativas, custo e limites no evidence do lead. Providers
  externos continuam opt-in por organização.

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
  (RE_ENRICH); a API repassa `routability_type` do contato,
  `prepare_event_actions` usa o mesmo critério e a UI exibe a recomendação
  no detalhe do lead (`NextActionCard` no `OverviewTab`).
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
  com deduplicação, early stopping, role fit por título, orçamento e estados
  explícitos. `HunterPeopleProvider` e `WebsitePeopleProvider` são adapters
  reais; o site oficial só é registrado quando a organização declara
  `WEBSITE_PEOPLE_PROVIDER` com quota positiva em `api_quota`, e Hunter segue
  exigindo chave + quota explícitas.
- `NextBestActionService` recomenda uma ação explicável sem efeitos colaterais
  e a API a expõe em `GET /api/leads/{id}` como `next_best_action`; o envio
  continua humano no loop.
- Candidatos de discovery carregam provenance consolidada no `Lead`, incluindo
  providers, consultas, identificadores externos, plano e regra de identidade;
  merges automáticos ocorrem apenas por chaves fortes.

### Validação do snapshot

- `python -m pytest tests -q -W error`: **1097 passed, 19 skipped** (unit; testes com
  Postgres real rodam apenas com `E2E_DATABASE_URL`/banco ativo);
- E2E de ciclo completo (`tests/e2e_outreach_cycle.py`) contra o Postgres
  local reconstruido: **1 passed**;
- `python -m compileall -q services/api services/workers`: passou;
- Web: lint, TypeScript e build: passaram;
- `scripts/verify_migrations.py`: head único `4a6b8c9d1e2f`, incluindo propostas
  controladas e breakdown persistido do matcher;
- persistência controlada validada em PostgreSQL.

## Auditoria do banco (onda 3)

Problemas corrigidos e decisões (detalhes em `docs/pendencias-pos-consolidacao.md`):

- **Bug crítico:** `follow_up_versions` existia no modelo e era usada por
  `PATCH/GET /cadence/step`, mas nenhuma migration a criava → qualquer edição
  de etapa quebraria em runtime. Criada na migration `2c4e6f8a0d3e`.
- **Performance:** FKs usadas em leituras quentes estavam sem índice
  (`enrichments.lead_id`, `jobs.campaign_id/organization_id`,
  `persons.organization_id/company_id`, `event_opportunities.lead_id`,
  `commercial_outcomes.lead_id`, `notifications.lead_id`, `leads.company_id`)
  → 9 índices + um índice **parcial** para o claim da fila
  (`ix_jobs_pending_claim ON jobs(created_at) WHERE status='PENDING'`, usado
  por `_CLAIM_SQL` com `FOR UPDATE SKIP LOCKED`). Migration `2d5e7f9b1c3f`.
- **Segurança:** `_CLAIM_SQL` parametrizado (bound params);
  `organization_secrets` cifrado com Fernet; sem SQL bruto com concatenação;
  tenant-scope aplicado na camada de rotas (RLS do Postgres não ativado —
  decisão documentada). Em produção, `SECRETS_ENCRYPTION_KEY` agora é
  obrigatória: a derivação determinística pelo `DATABASE_URL` fica restrita a
  desenvolvimento/testes, com cobertura de regressão.
- **Todos os dados esperados:** divergência de colunas entre models e banco = 0; 37 tabelas;
  FKs verificadas; sem tabelas órfanas após o reset.
- **Integridade de histórico:** `follow_up_versions` possui constraint única em
  `(follow_up_id, version_number)` (`2e6f8a0c2d4e`), evitando versões duplicadas
  em edições concorrentes.
- **Idioma dos artefatos:** comentários e docstrings adicionados nesta
  auditoria foram mantidos em PT-BR, conforme a convenção do repositório.

**Próximo passo imediato**

Onda 0A (verdade documental) concluída: P1.32/P1.33 reconciliados como
operacionais, drifts F-01–F-04 registrados, fontes de verdade declaradas. O
próximo passo é a **Onda 0B** (grafo local + release blockers: reprodutibilidade,
placeholders, hardening, baseline de telas) e, na sequência, a **Onda 1**
(controlled learning com publicação/versionamento de `OfferProfile`) — nesta
ordem, antes do outreach assistido, conforme prioridade confirmada.