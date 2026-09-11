---
name: testing
description: Planejar, escrever e executar testes para o agente-prospeccao. Use em features, bug fixes, migrations, providers, API, workers, frontend e Definition of Done. Prioriza testes determinísticos e o menor conjunto que prove o comportamento.
---
# Testing

Teste comportamento/contrato, não detalhes acidentais.

## Comandos base
Da raiz: `python -m pytest tests -q`
Frontend: `cd apps/web && npm run lint && npx tsc --noEmit && npm run build`
Python: `python -m compileall -q services/api services/workers`
Migrations: `python scripts/verify_migrations.py`
E2E real depende de `E2E_DATABASE_URL`.

## Cobertura por feature
Happy path + empty + invalid + provider failure + retryable failure + unknown + tenant isolation + duplicate/idempotency + budget/quota quando relevante.

Providers nunca chamam API paga/real em testes normais. Use fake/stub no seam.

Learning/scoring: fórmula/profile version, absence vs negative, snapshot, não contaminação por fallback, amostra mínima.

Reporte comandos realmente executados, resultado, skips e o que não foi executado.
