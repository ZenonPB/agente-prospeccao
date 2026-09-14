# Mapa de status — fonte de verdade operacional

> **LIVE · atualizado em 2026-09-14.** Código/migrations/testes prevalecem.
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
| Event discovery | ✅ | eventos normalizados, contexto declarativo, matching, timing/expiração e ação recomendada. |
| Event Intelligence | ✅ | regras fora do core, contexto MEJ/esportivo/fallback, séries recorrentes, demanda inferida e persistência PostgreSQL. |
| Pre-scoring | ✅ | config declarativa, auditoria de descartes e provenance. |
| Enrichment waterfall | ✅ | steps/estratégia/custo/gates declarativos. |
| OfferProfile base | ✅ | catálogo validado + ofertas AlphaMec. |
| Prospecting Intelligence / Golden Paths | ✅ | landing page, sistemas web, engenharia e troféus com quality gates, UNKNOWN≠FALSE, benchmark de regressão e gate CI. |
| Golden Path troféus/eventos/MEJ | ✅ | contexto MEJ/esportivo declarativo, timing comercial, oferta específica, idempotência e E2E PostgreSQL; conversão real ainda depende de campanha. |
| OfferProfile versionado por workspace | ✅ | publicação controlada, single-active e rollback exato. |
| OfferProfile efetivo no pipeline inteiro | ✅ | registry efetivo tenant-safe por job; discovery/enrichment/scoring consomem overlay da organização. |
| OfferMatcher + snapshots | ✅ | matcher-v2, score breakdown, quality gates e histórico append-only. |
| Opportunity attribution | ✅ | conversion/outcome ligados à oportunidade/versão/snapshot. |
| Next Best Action | ✅ | decisão persistida + roteabilidade + tarefas. |
| Sequences | ✅ | templates/versionamento/enrollment/execution. |
| Workflows | ✅ | definições/runs auditáveis; sem segundo caminho oculto de envio. |
| Kanban comercial | ✅ | estágios, owner e operações existentes. |
| Feedback útil/não útil | ✅ | motivo fechado, org-scoped, auditável. |
| Score feedback | ✅ | feedback numérico humano e trilha. |
| Controlled learning | ✅ | comparação → proposta → aprovação → publicação → rollback. |
| CRM adapters/sync | ✅ | Pipedrive/HubSpot/Salesforce, idempotência e certificação read-only quando há credenciais. |
| Opportunity 360 read-only | ✅ | tenant-safe, timeline e query-count testado em PostgreSQL. |
| Company 360 | ✅ | leitura + edição canônica allowlist, concorrência otimista, auditoria e UI. |
| Person 360 | ✅ | leitura + edição/validação humana, concorrência otimista, auditoria e UI. |
| Opportunity 360 editável | ✅ | comandos canônicos, RBAC, tarefas idempotentes/race-safe, editor web e suíte PostgreSQL no CI. |
| Importador histórico AlphaMec | ✅ | lifecycle CSV/XLSX com preview/mapping/dry-run, dedupe conservador, contexto comercial histórico, confirmação idempotente, relatório por linha e E2E PostgreSQL. |
| Sales Operating System — Bloco B | ✅ | Central comercial, fila diária, busca global, carteira operacional, saved views, tags/arquivamento, bulk de estágio/campanha/sequência/tarefas, export auditável e RBAC/tenant isolation. |
| Filter Context compartilhado | ✅ | contrato único URL/API para período, campanha, consultor, oferta/versão, canal, status, score, outcome, atribuição, busca, segmento, cidade/UF e estágio de negociação. |
| BI interativo final | ✅ | analytics/export usam o mesmo Filter Context; filtros server-side/restauráveis, saved views e cross-filter sobre as dimensões comerciais principais. |
| Coaching comercial | 🟠 | sinais/tarefas/feedback existem; falta produto de coaching consolidado. |
| UAT multi-workspace | 🟠 | testes automatizados fortes; falta sessão UAT formal do RC. |
| Campanha real AlphaMec | ⬜ | não declarar concluída sem execução autorizada/evidência real. |

## Limites do estado atual

- O benchmark do Bloco A é **sintético e de regressão**. Ele protege roteamento, evidência, genericidade e confiança, mas não prova conversão comercial.
- O Bloco B está tecnicamente fechado como sistema operacional de vendas; smoke/browser e validação com usuários reais permanecem parte do UAT do RC, não uma lacuna de consistência do domínio.
- `precision@20`, resposta, reunião, proposta, contrato e receita só podem ser afirmados após campanhas reais com outcomes atribuídos.
- Contexto de evento e estimativas derivadas permanecem `INFERENCE`; ausência de evidência permanece `UNKNOWN`.

## Bloqueadores antes da calibração final

1. UAT multi-workspace com overlays diferentes em jobs concorrentes e operações de CRM.
2. Amostra real suficiente antes de qualquer mudança automática de pesos.
3. Validar coaching/calibração com o fluxo comercial real da AlphaMec.
4. Rodar campanhas reais autorizadas para medir precisão e conversão por oferta.

## Próximo corte do RC

Coaching/calibração → UAT multi-workspace → campanha real autorizada/hardening final.
