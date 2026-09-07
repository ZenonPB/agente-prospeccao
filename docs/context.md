# Prospect.ai — Contexto vivo

> Leia este arquivo primeiro. Ele contém o estado atual; o histórico detalhado
> está em `docs/consolidacao.md` e `docs/roadmap-vendas.md`.
>
> **Snapshot:** 2026-09-07 · branch `feat/identidade-cross-provider` ·
> Alembic head `dd9e0f1a2b3c`.

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

### Capacidades entregues nesta consolidação

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
  `provider_execution_metrics`; custo real ainda é opcional e a quota continua
  sendo medida separadamente em `provider_usage`.
- Contatos persistem `identity_confidence`, `contact_confidence`, confiabilidade
  da fonte, status de verificação e classificação de acionabilidade (`DIRECT`,
  `ROUTABLE`, `INSTITUTIONAL` ou `UNKNOWN`).
- Candidatos de discovery carregam provenance consolidada no `Lead`, incluindo
  providers, consultas, identificadores externos, plano e regra de identidade;
  merges automáticos ocorrem apenas por chaves fortes.

### Validação do snapshot

- `python -m pytest tests -q -W error`: **948 passed**;
- `python -m compileall -q services/api services/workers`: passou;
- Web: lint, TypeScript e build: passaram;
- `scripts/verify_migrations.py`: head único `dd9e0f1a2b3c`;
- persistência controlada validada em PostgreSQL.

## Próximo passo imediato

Não habilitar provider externo por padrão. Priorizar identidade cross-provider
de empresas e People Discovery real para completar evento → decisor → outreach.
As demais prioridades estão em `docs/pendencias-pos-consolidacao.md`.