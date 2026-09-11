---
inclusion: fileMatch
fileMatchPattern: "services/**/*.py"
---
# Backend steering
- Workers async: `httpx.AsyncClient`, não `requests`.
- Config via settings; não ler environment diretamente.
- ORM canônico em `services/workers/src/database/models.py`.
- Preserve `organization_id` e tenant isolation.
- Não crie abstração paralela sem procurar a existente.
- Separe empty/failed/unknown/disabled/quota/budget.
- Preserve provenance, confidence e observabilidade.
- Não hardcode oferta no core.
