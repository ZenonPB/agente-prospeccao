# Baseline operacional

> **RUNBOOK · atualizado em 2026-09-13.** Define o mínimo para considerar um
> commit candidato ao AlphaMec RC.

## Build e testes

No mesmo HEAD candidato:

```bash
python -m compileall -q services/api services/workers
python -m pytest tests -q -W error
```

CI também precisa provar em PostgreSQL real:
- `alembic upgrade head`;
- segunda execução idempotente;
- `scripts/verify_migrations.py`;
- seed smoke;
- E2E crítico;
- concorrência de conversão;
- invariantes tenant/performance das visões CRM relevantes.

Frontend:

```bash
cd apps/web
npm ci
npm run lint
npx tsc --noEmit
npm run build
```

## Segurança

- JWT secret forte em produção;
- CORS sem localhost em produção;
- headers de segurança habilitados;
- secrets de provider por workspace;
- providers externos opt-in/quota;
- APIs tenant-sensitive filtram `organization_id` desde o recurso raiz;
- acesso cross-tenant conhecido retorna fail-closed;
- jobs nunca executam sem `organization_id` quando a operação é tenant-bound.

## Banco

- um único Alembic head;
- constraints/FKs/índices coerentes;
- migrations reproduzíveis do banco vazio;
- nenhuma migration manual fora da cadeia;
- query-count explícito em agregadores 360/listas críticas;
- importadores devem ser idempotentes e auditáveis.

## Runtime

- jobs longos fora da request;
- claim de job concorrente seguro;
- stale jobs recuperáveis;
- correlation ID/provider metrics disponíveis;
- OfferProfile efetivo do workspace aplicado ao pipeline;
- falha crítica de configuração não cai silenciosamente para configuração de outro tenant/global inadequada.

## Frontend

- loading/error/empty states;
- foco visível e teclado;
- labels/semântica adequados;
- links externos seguros;
- queries/cache centralizados;
- sem N+1 de requests no navegador;
- listas volumosas paginadas/filtradas no servidor;
- produção sem erros de typecheck/build.

## Observabilidade mínima

Para uma campanha/job deve ser possível responder:
- qual workspace/campanha/job/correlation ID;
- quais providers rodaram;
- status/latência/custo/uso;
- quantos candidatos e leads foram produzidos;
- qual OfferProfile/versão influenciou a oportunidade;
- qual erro/estágio falhou.

## Merge policy

Não mergear com suíte vermelha porque “já falhava antes”. Corrigir ou provar
que o gate oficial correto não executa aquele teste por uma razão documentada.
Todos os checks devem estar verdes no mesmo HEAD do merge.
