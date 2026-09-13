# Mapa de status — fonte de verdade operacional

> **LIVE · atualizado em 2026-09-13.** Código/migrations/testes prevalecem.
> Leia também `docs/README.md` e `docs/roadmap.md`.

Legenda: ✅ completo no escopo atual · 🟠 parcial · ⬜ pendente.

| Capability | Estado | Evidência / limite atual |
|---|---:|---|
| Multi-workspace + membership | ✅ | organization_id, org switcher, escopo de carteira, testes cross-tenant. |
| Secrets/quotas por workspace | ✅ | providers externos opt-in e resolução por organização. |
| Company canônica + aliases | ✅ | `companies`, `company_aliases`, resolução CNPJ/domínio/aliases. |
| Person canônica | ✅ | `persons`, confidence, verification, routability e vínculo à Company. |
| Discovery federado | ✅ | Places/CNAE/PNCP + adapters/registry/planner e métricas. |
| People discovery federado | ✅ | providers opt-in, role fit, gates de identidade/buyer role. |
| Event discovery | ✅ | eventos normalizados, matching, timing/expiração e ação recomendada. |
| Pre-scoring | ✅ | config declarativa, auditoria de descartes e provenance. |
| Enrichment waterfall | ✅ | steps/estratégia/custo/gates declarativos. |
| OfferProfile base | ✅ | catálogo validado + ofertas AlphaMec. |
| OfferProfile versionado por workspace | ✅ | publicação controlada, single-active e rollback exato. |
| OfferProfile efetivo no pipeline inteiro | ✅ | PR #172: ContextVar por job + registry efetivo tenant-safe + testes concorrentes. |
| OfferMatcher + snapshots | ✅ | matcher-v2, score breakdown e histórico append-only. |
| Opportunity attribution | ✅ | conversion/outcome ligados à oportunidade/versão/snapshot. |
| Next Best Action | ✅ | decisão persistida + roteabilidade + tarefas. |
| Sequences | ✅ | templates/versionamento/enrollment/execution. |
| Workflows | ✅ | definições/runs auditáveis; sem segundo caminho oculto de envio. |
| Kanban comercial | ✅ | estágios, owner e operações existentes. |
| Feedback útil/não útil | ✅ | motivo fechado, org-scoped, auditável. |
| Score feedback | ✅ | feedback numérico humano e trilha. |
| Controlled learning | ✅ | comparação → proposta → aprovação → publicação → rollback. |
| CRM adapters/sync | ✅ | Pipedrive/HubSpot/Salesforce, idempotência e certificação read-only quando há credenciais. |
| Opportunity 360 read-only | ✅ | PR #171; tenant-safe, timeline e query-count testado em PostgreSQL. |
| Company 360 read-only | ✅ | PR #172; backend + frontend + testes PostgreSQL. |
| Person 360 read-only | ✅ | PR #172; backend + frontend + testes PostgreSQL. |
| Opportunity 360 editável | ✅ | PR #173: comandos canônicos, RBAC, tarefas idempotentes/race-safe, editor web e suíte PostgreSQL no CI. |
| Importador histórico AlphaMec | ⬜ | precisa preview/mapping/validation/dedupe/import/report. |
| Filter Context compartilhado | ⬜ | dashboards ainda não usam um contrato único de filtros. |
| BI interativo final | 🟠 | analytics existem; falta Filter Context e UX integrada. |
| Coaching comercial | 🟠 | sinais/tarefas/feedback existem; falta produto de coaching consolidado. |
| Golden Path troféus/eventos/MEJ | 🟠 | peças existem; falta UAT de ponta a ponta e critérios de aceite finais. |
| UAT multi-workspace | 🟠 | testes automatizados fortes; falta sessão UAT formal do RC. |
| Campanha real AlphaMec | ⬜ | não declarar concluída sem execução autorizada/evidência real. |

## Bloqueadores antes da calibração final

1. Implementar importação histórica segura antes de abandonar a planilha como fonte de transição.
2. UAT multi-workspace com overlays diferentes em jobs concorrentes e operações de CRM.
3. Amostra real suficiente antes de qualquer mudança automática de pesos.
4. Validar Filter Context e BI com o fluxo comercial real da AlphaMec.

## Próximo corte do RC

Importador histórico → Filter Context/BI → coaching/calibração → Golden Path → UAT → campanha real/hardening.
