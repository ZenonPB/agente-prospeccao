---
name: release-operations
description: Auditar release, deploy e operação do agente-prospeccao em Render, Vercel, Neon, Docker e CI sem assumir AWS ou executar mutações externas.
---
# Release & Operations

Use esta skill para preparar, revisar ou diagnosticar releases do stack atual. O alvo oficial é Render/Vercel/Neon, com Docker Compose para desenvolvimento local; não assuma AWS, Terraform, Kubernetes ou outro provedor sem evidência nos arquivos do projeto.

## Segurança operacional
- Nunca imprimir, copiar ou testar valores de secrets; valide somente nomes, presença e formato não sensível.
- Não executar deploy, restart de produção, migration destrutiva, alteração de DNS, exclusão de dados ou mudança de infraestrutura sem confirmação explícita.
- Classifique cada comando como leitura, validação local, CI, staging ou produção.
- Não use um health check verde como prova de que workers, scheduler, jobs ou WebSocket estão funcionando.

## Pré-voo
1. Leia `AGENTS.md`, `docs/context.md`, `docs/architecture.md`, `docs/decisions.md` e `DEPLOY.md`.
2. Confirme o commit/release e o ambiente alvo.
3. Compare nomes de env vars entre `.env.example`, API, workers, web, `render.yaml` e documentação sem revelar valores.
4. Verifique CI: lint, typecheck, build, compileall, pytest, migrations e E2E quando aplicável.
5. Verifique compatibilidade expand/contract: migration antes do código consumidor, backfill idempotente e rollback sem depender de downgrade destrutivo.

## Ordem e smoke
- Banco/migration compatível → API → workers/jobs consumer/scheduler → web.
- Confirme readiness da API, autenticação JWT, uma rota REST org-scoped, reivindicação de job, progresso no WebSocket e uma leitura do frontend.
- Distingua API viva, worker vivo, scheduler ativo, job processado e provider externo disponível.
- Use dados sintéticos e providers fake/stubados; não dispare outreach nem chamadas pagas em smoke normal.

## Observabilidade e rollback
- Procure correlation_id, job_id, organization_id redigido, duração, estado, retryability, quota/custo e erro estruturado.
- Não coloque PII ou secrets em logs, mensagens de erro, evidências ou artefatos de CI.
- Para falha, preserve evidência, identifique último ponto saudável e proponha rollback compatível com migrations.
- Backup só conta quando restore em ambiente seguro for verificável; não declare backup válido apenas pela existência de um arquivo.

## Saída
Reporte: ambiente, commit, checks executados, resultado, riscos P0-P3, comandos seguros reproduzíveis, confirmação necessária e próximo passo. Nunca classifique como pronto se apenas o scaffold existe.
