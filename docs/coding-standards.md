# Coding standards

> **LIVE · atualizado em 2026-09-13.** Complementa AGENTS.md e os padrões dos
> subdiretórios. Segurança de tenant e fonte canônica têm prioridade sobre
> conveniência local.

## Backend

- Python tipado onde melhora contrato/leitura; nomes explícitos.
- Rotas finas; composição de domínio em services.
- Toda query tenant-sensitive começa por `organization_id`.
- Evitar lazy-loading acidental/N+1; usar batch queries/joinedload quando
  necessário e teste de query-count em agregadores críticos.
- Não ocultar erro crítico com fallback global inseguro.
- Operação repetível deve ser idempotente por constraint/chave lógica.
- Transações e commits pertencem a boundary explícita.
- Provider externo: timeout, quota, opt-in, tratamento de erro e telemetria.
- Nunca logar secret/token/PII desnecessária.

## Domínio

Antes de tabela nova, procurar fonte canônica em Company/Person/Lead/
LeadOpportunity/Task/Activity/Outcome/OfferProfile. Preferir derivação em leitura
quando não há ciclo de vida próprio.

`UNKNOWN` não vira `FALSE`; evidência e hipótese permanecem distintas.

## Frontend

- TypeScript sem `any` salvo integração inevitável/documentada.
- React Query para estado de servidor e invalidação por domínio.
- Componentes acessíveis: elemento semântico, label, foco visível, teclado,
  `aria-*` quando necessário e target de interação adequado.
- Estados loading/error/empty sempre que houver fetch.
- Não usar efeitos/fetch duplicados para dados já cacheados.
- Listas pesadas: paginação/filtro server-side.
- Links externos normalizados e `rel="noreferrer"`/`noopener` conforme caso.
- UI é comercial: traduzir keys técnicas e priorizar hierarquia visual.

## API

- contratos estáveis e explícitos;
- erro 404 fail-closed quando revelar existência cross-tenant seria informação;
- validação Pydantic para payloads;
- limites de tamanho/paginação;
- response não expõe metadata interna/secrets;
- filtros compartilhados devem ser aplicados no backend.

## Testes

Mudança de domínio exige teste do happy path e das invariantes que podem
regredir. Para multi-workspace, incluir cenário A vs B. Para persistência/
constraints/query-count, usar PostgreSQL real no gate apropriado.

Não “consertar” teste enfraquecendo assertion só para ficar verde.

## Commits e PR

- branch curta por fatia/batch coerente;
- commits descritivos por responsabilidade;
- PR inicia draft quando ainda há gates pendentes;
- body descreve escopo, segurança, testes, migrações e docs;
- só marcar ready/merge com CI final verde no mesmo HEAD.

## Gates

```bash
python -m compileall -q services/api services/workers
python -m pytest tests -q -W error
cd apps/web && npm ci && npm run lint && npx tsc --noEmit && npm run build
```

Além disso: migrations + verifier + E2E/invariantes PostgreSQL no CI.
