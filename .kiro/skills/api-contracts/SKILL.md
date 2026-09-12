---
name: api-contracts
description: Verificar compatibilidade dos contratos REST e WebSocket entre Next.js, FastAPI, jobs e modelos persistidos sem inventar endpoints.
---
# FastAPI ↔ Next Contract Verification

Use esta skill antes de alterar uma rota, payload, autenticação, WebSocket, migration consumida pela API ou tela que depende de dados do backend.

## Fonte da verdade
- Leia `AGENTS.md`, `apps/web/AGENTS.md`, `docs/architecture.md`, `docs/business-rules.md` e `docs/decisions.md`.
- Encontre a rota FastAPI real, schema/status/erro, dependency de auth, consumidor web real, tipos/normalização e testes existentes.
- Modelos são definidos uma única vez em `services/workers/src/database/models.py`; a API os reexporta.
- Não crie endpoint, campo, enum, status ou fallback com base apenas no nome esperado pelo frontend.

## Checklist REST
Para cada operação, registre método, caminho, query/path/body, resposta de sucesso, estados empty/partial/failed, códigos HTTP, payload de erro, autenticação, organization scope, paginação, ordenação e efeitos de mutação.
- Verifique se o cliente trata loading, empty, error e partial sem confundir ausência com falha.
- Preserve compatibilidade de campos e enums; mudanças breaking exigem estratégia explícita.
- Confirme idempotência, correlation_id, retryability e efeitos no job quando a request apenas enfileira trabalho.
- Não faça chamada a provider real/pago para validar contrato normal.

## Checklist WebSocket
- Confirme o caminho real e o protocolo de primeira mensagem `{"type":"auth","token":"..."}`.
- O token não deve ir na query string.
- Valide ownership do job, organização, eventos de progresso, terminal states, reconnect e erro de autenticação.
- Teste desconexão, mensagem duplicada, job inexistente e job de outro tenant.

## Persistência e integração
Ao mudar contrato, procure migration, serializer, repositório, cache, analytics, export, auditoria e consumidores. Separe alteração de schema expand-compatible da remoção posterior. Verifique que falha do provider, quota, budget, configuração e ausência de dados não viram o mesmo payload.

## Evidência
Produza uma tabela rota/consumidor/teste/status e uma lista de incompatibilidades com arquivo/linha. Exija fixture ou teste de integração determinístico para cada cenário relevante e atualize documentação quando o contrato público mudar. Não declare compatível porque TypeScript ou lint passou isoladamente.
