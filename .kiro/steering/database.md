---
inclusion: fileMatch
fileMatchPattern: "services/workers/**/*"
---
# Database steering
- Nova migration; não reescrever migration compartilhada.
- Prefira expand-compatible.
- Avalie índices para FKs/hot paths.
- Preserve histórico/versionamento em scoring/learning.
- Teste tenant isolation.
- Valide migration chain.
- Backfill idempotente e sem inventar dado.
