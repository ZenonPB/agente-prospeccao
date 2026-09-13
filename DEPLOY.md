# Deploy — Prospect.ai

> Atualizado em 2026-09-13. Este runbook evita depender de preços/limites de
> planos de terceiros, que mudam com frequência. Consulte o provedor escolhido
> no momento do deploy. `.env.example`, Dockerfiles e manifests do repositório
> são a fonte técnica atual.

## Topologia recomendada

```text
Browser
  ↓ HTTPS
Next.js Web
  ↓ HTTPS + JWT + X-Organization-Id
FastAPI API
  ├─ job consumer / schedulers no mesmo runtime atual
  └─ providers externos opt-in
  ↓
PostgreSQL 16
```

A aplicação pode ser hospedada em provedores diferentes (por exemplo frontend
serverless + backend container + PostgreSQL gerenciado), desde que os requisitos
abaixo sejam atendidos. Não assuma URLs fixas do projeto.

## Pré-deploy

O **mesmo commit** a publicar deve estar verde no CI:

- backend compile + `pytest -W error`;
- migrations PostgreSQL real + segunda execução + schema verifier + seed smoke;
- E2E/invariantes críticos;
- web lint + typecheck + production build.

Também confirme:
- migrations em um único `head`;
- backups/restore testados para o banco alvo;
- secrets fora do Git;
- domínio/API final conhecidos para CORS/tracking;
- providers externos habilitados somente onde autorizados.

## Banco

Use PostgreSQL 16 compatível e configure `DATABASE_URL`.

Antes de subir a aplicação:

```bash
cd services/workers
alembic upgrade head
cd ../..
python scripts/verify_migrations.py --database-url "$DATABASE_URL"
```

A migration deve ser executada por **um** passo de release controlado. Evite que
várias réplicas tentem migrar simultaneamente no startup.

## API

O processo HTTP é iniciado a partir de `services/api` com Uvicorn, respeitando a
porta fornecida pelo ambiente de hospedagem, por exemplo:

```bash
cd services/api
uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
```

O runtime atual também inicia loops/schedulers e o job consumer no lifespan.
Antes de escalar horizontalmente, valide semanticamente cada scheduler; o claim
de jobs usa mecanismo concorrente, mas nem todo loop periódico precisa rodar em
N réplicas.

## Frontend

Root: `apps/web`.

```bash
npm ci
npm run build
npm run start
```

Configure `NEXT_PUBLIC_API_URL` para a URL pública HTTPS da API e as variáveis de
autenticação exigidas pelo frontend atual.

## Variáveis sensíveis

Não mantenha uma lista duplicada aqui: use `.env.example` como contrato. Em
produção, no mínimo revise estas categorias:

- PostgreSQL;
- JWT/session secrets;
- encryption key para secrets BYOK;
- CORS/origens e URLs públicas;
- providers/LLMs habilitados;
- SMTP/tracking/inbound webhook quando usados;
- limites/poll intervals operacionais.

Use secret manager do provedor. Nunca exponha chave server-side via variável
`NEXT_PUBLIC_*`.

## Multi-workspace e providers

Chaves/configurações globais de infraestrutura não substituem secrets por
workspace quando o produto usa BYOK/opt-in. Após deploy, teste com duas
organizações diferentes:

- headers/sessão selecionam o workspace correto;
- providers e quotas são resolvidos por organização;
- OfferProfile publicado de A não aparece em B;
- CRM/analytics não vazam dados cross-tenant.

## CORS e hosts

`CORS_ORIGINS` deve conter somente origens reais permitidas. Em produção, a API
rejeita configuração com localhost. Trusted Hosts/security headers são ativados
conforme settings atuais.

Não edite código para adicionar domínio fixo: configure via ambiente.

## Health check

Endpoint:

```text
GET /health
```

Sucesso esperado inclui banco acessível. Um healthcheck sem DB não é suficiente
para considerar a API saudável.

## Smoke pós-deploy

1. `/health` retorna sucesso;
2. login/session funcionam;
3. selecionar workspace A/B funciona;
4. criar/listar campanha sem vazamento;
5. rodar job pequeno e acompanhar estado;
6. abrir oportunidade/CRM 360;
7. conferir logs/correlation IDs;
8. validar um provider autorizado;
9. confirmar que secrets não aparecem em respostas/logs;
10. executar UAT do `docs/uat-runbook.md` antes de rollout real.

## Backup e rollback

- automatize dumps/snapshots do PostgreSQL conforme o provedor;
- teste restore, não apenas criação de backup;
- mantenha commit/imagem de release identificável;
- rollback de aplicação não deve tentar downgrade destrutivo de schema sem plano;
- OfferProfile tem rollback próprio versionado no domínio.

## Observabilidade

Acompanhe no mínimo:
- taxa/latência/5xx da API;
- jobs pending/in-progress/failed e stale recovery;
- conexões/CPU/storage do Postgres;
- provider errors/quota/custo/latência;
- bounce/routability se outreach estiver habilitado;
- correlation IDs de incidentes.

## Escala

Antes de aumentar réplicas:
- medir gargalo real;
- conferir pool de conexões;
- garantir singleton/lock adequado para schedulers periódicos;
- testar claims concorrentes de jobs;
- evitar que scale-to-zero interrompa requisitos de processamento periódico.

## Incidente

Se houver suspeita de vazamento de tenant, envio indevido ou secret exposto:

1. interromper capacidade afetada;
2. rotacionar credenciais quando aplicável;
3. preservar logs/auditoria;
4. identificar workspace/entidades/correlation IDs;
5. corrigir e adicionar teste de regressão;
6. só reabilitar após validação.
