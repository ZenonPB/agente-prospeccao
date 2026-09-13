# Mapa de status — fonte de verdade operacional

> **LIVE · atualizado em 2026-09-13.** Código/migrations/testes prevalecem.
> Leia também `docs/README.md` e `docs/roadmap.md`.

Legenda: ✅ completo no escopo atual · 🟡 em validação/PR · 🟠 parcial · ⬜ pendente.

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
| OfferProfile efetivo no pipeline inteiro | 🟡 | PR #172: ContextVar por job + registry efetivo; falta CI final/merge. |
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
| Company 360 read-only | 🟡 | PR #172; backend + frontend + testes PostgreSQL em validação. |
| Person 360 read-only | 🟡 | PR #172; backend + frontend + testes PostgreSQL em validação. |
| Opportunity 360 editável | 🟠 | fontes de edição existem, falta contrato/UI unificados. |
| Importador histórico AlphaMec | ⬜ | precisa preview/mapping/validation/dedupe/import/report. |
| Filter Context compartilhado | ⬜ | dashboards ainda não usam um contrato único de filtros. |
| BI interativo final | 🟠 | analytics existem; falta Filter Context e UX integrada. |
| Coaching comercial | 🟠 | sinais/tarefas/feedback existem; falta produto de coaching consolidado. |
| Golden Path troféus/eventos/MEJ | 🟠 | peças existem; falta UAT de ponta a ponta e critérios de aceite finais. |
| UAT multi-workspace | 🟠 | testes automatizados fortes; falta sessão UAT formal do RC. |
| Campanha real AlphaMec | ⬜ | não declarar concluída sem execução autorizada/evidência real. |

## Bloqueadores antes da calibração final

1. Merge seguro do OfferProfile efetivo por workspace no pipeline.
2. Não permitir que learning/scoring use catálogo global quando existe versão publicada.
3. UAT multi-workspace com overlays diferentes em jobs concorrentes.
4. Amostra real suficiente antes de qualquer mudança automática de pesos.

## Próximo corte do RC

Após PR #172: Opportunity 360 editável → importador histórico → Filter Context/BI → coaching/calibração → Golden Path → UAT → campanha real/hardening.
