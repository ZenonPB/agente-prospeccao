---
inclusion: fileMatch
fileMatchPattern: "tests/**/*"
---
# Testing steering
- Testes determinísticos.
- Não chamar provider real/pago em teste normal.
- Cubra unknown/empty/failure quando relevante.
- Inclua tenant isolation em features multi-tenant.
- Teste idempotência de jobs/migrations/imports.
- Só reporte comandos realmente executados.
