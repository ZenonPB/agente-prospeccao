# Fechamento das lacunas de Data Intelligence

Este complemento fecha quatro limites deliberados das Fases 3+4: histórico de vínculo profissional, verificação de e-mail com catch-all e histórico, coleta externa de jobs/news/social e monitoramento contínuo.

## Employment canônico

`EmploymentHistoryService` mantém na entidade canônica `Person` três estruturas versionáveis em `raw_data`: `employment_history`, `current_employment` e `employment_changes`. A mesma empresa+cargo é um heartbeat idempotente; mudança de cargo e mudança de empregador são eventos distintos. Snapshots anteriores recebem `ended_at` e nunca são sobrescritos.

Uma mudança confirmada gera evidência `employment_change`, convertida pela engine em `JOB_CHANGE` ou `ROLE_CHANGE`. O Data Health usa `current_employment.last_seen_at` como freshness de emprego, em vez de reutilizar genericamente `Person.last_verified_at`.

## Email Verification v2

A validação passiva continua fazendo sintaxe, domínio descartável e MX. MX válido agora significa `domain_validated`, não caixa individual verificada. O resultado rico separa:

- `invalid`;
- `unknown`;
- `domain_validated`;
- `catchall_unknown`;
- `catch_all`;
- `deliverable`.

O histórico fica em `Person.raw_data.email_verification_history`, com limite de snapshots. Data Health usa o timestamp desse histórico.

O probe SMTP de catch-all é uma interação ativa e exige duas autorizações simultâneas:

1. `EMAIL_CATCHALL_PROBE_ENABLED=true` no ambiente;
2. `EMAIL_CATCHALL_PROBE > 0` em `Organization.api_quota`.

Sem as duas condições, nenhum probe SMTP é executado. Falha de probe nunca vira e-mail verificado.

## Feeds externos de intent

Há um adapter HTTP comum para três famílias:

| Família | Endpoint | Quota do workspace |
|---|---|---|
| vagas / emprego | `JOB_INTENT_URL` | `JOB_INTENT_HTTP` |
| notícias corporativas | `NEWS_INTENT_URL` | `NEWS_INTENT_HTTP` |
| sinais sociais | `SOCIAL_INTENT_URL` | `SOCIAL_INTENT_HTTP` |

Tokens Bearer opcionais usam `*_INTENT_TOKEN`. O contrato aceita uma lista JSON ou `{ "items": [...] }`. Cada item pode informar `title`, `description`, `url`, `external_id`, `observed_at`, `confidence`, `source_reliability` e, no feed de jobs, um objeto `employment` para atualização do vínculo da pessoa principal.

Segurança do adapter: HTTPS obrigatório, sem redirects, sem credenciais embutidas, sem fragments, DNS revalidado antes da chamada e rejeição de localhost ou qualquer IP não global. Tokens não são persistidos em evidências nem logs.

## Monitoramento contínuo

O scheduler executa a cada `CONTINUOUS_INTELLIGENCE_POLL_SECONDS`, mas workspaces continuam desabilitados por padrão. Para uma organização participar é obrigatório `CONTINUOUS_INTELLIGENCE > 0` em `api_quota`. Cada feed possui ainda sua própria cota, também opt-in.

Outras proteções:

- intervalo mínimo por workspace (`CONTINUOUS_INTELLIGENCE_MIN_INTERVAL_HOURS`);
- batch máximo (`CONTINUOUS_INTELLIGENCE_BATCH_SIZE`);
- deduplicação de evidências;
- telemetria em `provider_execution_metrics`;
- quotas contabilizadas por provider;
- recompute do Opportunity Vector somente quando há evidência nova;
- isolamento por `organization_id` em todas as leituras operacionais.

Gestores podem executar `POST /api/data-intelligence/watch/run-once`. A rota ignora apenas o intervalo temporal; nunca ignora opt-in nem quota.

## Defaults de custo

Os defaults abaixo são zero e, portanto, não geram consumo externo após deploy:

- `CONTINUOUS_INTELLIGENCE`;
- `JOB_INTENT_HTTP`;
- `NEWS_INTENT_HTTP`;
- `SOCIAL_INTENT_HTTP`;
- `EMAIL_CATCHALL_PROBE`.

Isso mantém a estratégia free-first: a infraestrutura de monitoramento existe e é operacional, mas só usa fontes configuradas e explicitamente habilitadas pelo workspace.

## O que exige UAT externo

A aplicação e os contratos podem ser validados integralmente em CI com mocks e PostgreSQL real. A qualidade de um feed específico (cobertura, latência, precisão e limites comerciais) só pode ser validada depois que um endpoint/token real for configurado. Isso é uma dependência operacional do provider, não uma lacuna do mecanismo de coleta.
