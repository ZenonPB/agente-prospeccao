---
name: backend-feature
description: Implementar ou evoluir features backend em services/api e services/workers usando FastAPI, Python async, SQLAlchemy e serviços existentes. Use para endpoints, services, workers, pipeline, orchestration, CRM, scoring, discovery, intent, learning e integrações internas.
---
# Backend Feature

## Antes de implementar
Siga `AGENTS.md`: consulte Graphify quando disponível, leia `docs/context.md` e documentação de arquitetura/regras/decisões conforme necessidade. Procure implementação existente por conceito.

## Anti-duplicação
Antes de criar Service, Provider, model, endpoint paralelo, enum, orchestration ou DTO, prove que a estrutura existente não suporta a mudança. Prefira evoluir o contrato atual.

## Regras do repo
- Workers são a fonte única de models/migrations.
- API reexporta models.
- IO em workers é async.
- Config via settings.
- Orquestração nos pontos já definidos pelo projeto.

## Estados e contratos
Não colapse `ok`, `empty`, `failed`, `disabled`, `quota_exceeded`, `invalid_request`, `configuration_error`, `budget_exceeded` quando semanticamente diferentes.
Preserve provenance, source, observed_at, confidence, retryability, cost/usage e correlation_id quando aplicável.

## Multi-tenancy
Toda leitura/mutação organizacional precisa de escopo explícito em query, service, endpoint, background job, cache e analytics.

## Epistemologia
Preserve FACT, INFERENCE, HYPOTHESIS e UNKNOWN. Ausência de evidência não é evidência negativa.

## Fluxo
contrato → teste falhando → implementação mínima → integração → observabilidade → regressão → docs.

## Proibido
network oculto em função pura; `requests` em worker async; `print` em service; hardcode de oferta no core; fallback silencioso que contamina learning; exception ampla virando "sem dados".
