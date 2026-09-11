# Baseline operacional (Task 1 — reproduzível, observável e seguro)

Este documento é o contrato da fundação sobre a qual as demais fases do roadmap
são construídas. Ele descreve como reproduzir o ambiente, como validar a cadeia
de migrations, como uma execução é correlacionada fim-a-fim e quais controles de
segurança são obrigatórios. Não substitui `QUICKSTART.md`/`DEPLOY.md`; consolida
as garantias operacionais.

## 1. Setup reproduzível

- Setup local: `scripts/setup.sh` (Linux/macOS) ou `scripts/setup.ps1` (Windows).
- Subir o ambiente: `scripts/dev.sh` / `docker-compose.yml`.
- Variáveis de ambiente: ver `.env.example`. Providers pagos são opcionais — o
  sistema sobe e opera com chaves vazias/dummy (ver seção 5).
- Dependências de teste: `requirements-dev.txt`.

## 2. Migrations verificáveis

- A cadeia Alembic deve ter **exatamente um head** (`scripts/verify_migrations.py`
  falha caso contrário).
- `services/workers/migrations/versions/3b6c8d0e1f2a_controlled_learning_proposals.py`
  declara `depends_on = "fe4f5a6b7c8d"` para garantir que `commercial_comparisons`
  exista antes da FK, em banco vazio.
- Validação de contrato de schema (tabelas, colunas, índices, FKs e uniques
  essenciais): `python scripts/verify_migrations.py --database-url "$DATABASE_URL"`.
- CI (`.github/workflows/ci.yml`, job `migrations`):
  1. `alembic upgrade head` em Postgres limpo;
  2. `alembic upgrade head` novamente (idempotência);
  3. `verify_migrations.py` (contrato de schema);
  4. seed de templates (smoke).

### Downgrade — não-objetivo consciente

`verify_migrations.py` não executa downgrade e várias migrations são guardadas/
idempotentes por desenho (correções de dados, criação condicional). Downgrade
automático **não** faz parte do baseline; recuperação se dá por restauração de
backup (`scripts/backup.sh`). O roadmap prevê downgrade apenas "quando suportado".

## 3. Observabilidade e correlação fim-a-fim

Uma execução pode ser reconstruída a partir de um único identificador:

```
request HTTP (X-Request-ID)
  -> job (job_id, organization_id, campaign_id)
     -> provider attempts (provider_execution_metrics.correlation_id)
```

- **Request**: `CorrelationIdMiddleware` (`services/api/src/middleware/correlation.py`)
  atribui/propaga `X-Request-ID` (aceita também `X-Correlation-ID` na entrada) e
  o devolve na resposta. O id fica num `ContextVar` acessível durante a request.
- **Logs estruturados**: `observability.log_event` emite `event=<name> k=v ...`
  em uma linha, com **redaction** de credenciais (`authorization`, `api_key`,
  `password`, `secret`, `token`) e inclui automaticamente `request_id` quando há
  uma request corrente. `log_job_event` correlaciona `job_id`/`organization_id`/
  `campaign_id` e mede `duration_ms`.
- **Provider trace**: `provider_execution_metrics.correlation_id` liga as
  medições de uma mesma execução; consultável em
  `GET /api/analytics/provider-trace/{correlation_id}` (com escopo de tenant).
- **Health**: `GET /health` faz ping real no banco (200 ok / 503 degradado).

## 4. Isolamento multi-tenant

Todo dado e ação são escopados por `organization_id`. Coberto por testes de
resolução de organização, acesso restrito por papel e escopo de tenant no
provider trace. Novos fluxos devem manter o escopo explícito.

## 5. Segurança e compliance (obrigatórios)

- **Sem provider pago obrigatório**: CI e testes rodam com chaves dummy/vazias.
- **Webhook inbound assinado**: requisição sem segredo válido → 401.
- **Opt-out / suppression / bounce**: bloqueiam envio; entregabilidade pausa
  auto-send por org quando bounce rate excede o limite.
- **Auditoria**: `OrgAuditLog`/`OrgAuditEvent` registram actor/target; segredos
  são auditados por `key_name` (`SECRET_SET`) — nunca o valor.
- **Headers de segurança**: `SecurityHeadersMiddleware` em todas as respostas.
- **Segredos**: nunca logados (redaction) nem persistidos em claro.

## 6. Como validar o baseline

```bash
# Testes unitários (sem banco)
python -m pytest tests -q

# Contrato de migrations (requer Postgres)
python scripts/verify_migrations.py --database-url "$DATABASE_URL" --upgrade
```

Critérios de aceite da Task 1: ambiente limpo conclui setup e migrations, o
healthcheck responde, uma execução é rastreável por correlação (request → job →
provider) e dados/ações de uma organização não vazam para outra.
