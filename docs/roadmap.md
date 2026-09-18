# Roadmap — AlphaMec 1.0

> **LIVE · atualizado em 2026-09-18.** Baseline: `main@446ca886f4a22addc672df9355ea59972bc86e2a`.

## Objetivo

Finalizar a 1.0 para uso real da AlphaMec sem continuar expandindo o produto horizontalmente. A prioridade é provar e fechar um Golden Path completo, confiável, explicável e learning-ready.

## Fundação já entregue

Multi-workspace/RBAC; Company/Person/Lead/LeadOpportunity; Vertentes/OfferProfile efetivo; discovery e Registry; entity resolution; pre-scoring/enrichment/scoring/OfferMatcher; Public Web; People/Contact; Commercial Dimensions shadow; Next Best Action; CRM/tasks/sequences/workflows/Kanban; importação histórica; BI/Filter Context; outcomes/feedback; controlled learning; UAT e production rehearsal.

## Reta final

### R1 — Preparação offline do Data Engine — AGORA
Sem depender de arquivos reais: sincronizar docs, contratos, fixtures, fail-closed, scope, manifest, checklist, critérios e runbook. Não declarar validação operacional.

### R2 — Piloto oficial do Registry — BLOQUEADO POR DADO REAL
Snapshot oficial congelado; manifest/hash; import scoped; auditoria pré-ACTIVE; ativação explícita; busca; amostra humana; métricas de download/raw/database/memória/tempo/qualidade/custo.

Golden Path congelado: Landing Pages → clínicas de psicologia → Araraquara/SP → CNAE 8650-0/03 → ativas; zero outreach.

### R3 — Evidence Contract
Auditar o que já existe em provenance, Opportunity Vector, web facts, snapshots e scoring. Consolidar somente lacunas reais para rastrear FACT/INFERENCE/HYPOTHESIS/UNKNOWN, source, confidence e observed_at.

### R4 — AI Commercial Analyst
Evoluir o motor existente, não criar um segundo scoring. A análise deve responder com evidência: por que empresa, por que oferta, por que agora, hipóteses, contraevidências, unknowns e abordagem sugerida. Aplicar raciocínio caro apenas depois de filtros baratos.

### R5 — Learning-ready persistence
Preservar Vertente/versão, evidências, analysis/policy/prompt/model version quando aplicável, timestamps, score/snapshot e outcome attribution. Reusar controlled learning existente.

### R6 — Real E2E AlphaMec
Empresa real → discovery → evidence → análise → oportunidade → pessoa → contato → CRM. Depois de validar dados, executar campanha autorizada separadamente para medir outcomes reais.

### R7 — Hardening + deploy
Corrigir P1/P2, rodar gates do mesmo HEAD, migrations/backup/restore, secrets/quotas/budget, observabilidade, deploy e smoke AlphaMec.

## Deferred pós-1.0

BigQuery produtivo/remote discovery amplo, Autopilot, Relationship Intelligence, omnichannel avançado, WhatsApp automático, Meeting/Proposal Intelligence, billing SaaS, scheduler nacional sofisticado, novos CRMs e expansão não necessária de Vertentes/providers.

## Gates

Toda entrega: testes do domínio; compileall; pytest `-W error`; PostgreSQL/migrations/idempotência/verifiers/E2E quando aplicável; web lint/typecheck/build quando afetado; tenant isolation; docs LIVE; mesmo HEAD verde.

## Critério final

A 1.0 não termina quando “todos os módulos existem”. Termina quando a AlphaMec consegue executar o Golden Path real com dados confiáveis, explicações rastreáveis, CRM operacional, custo controlado e outcomes capturáveis sem depender de intervenção técnica no fluxo normal.
