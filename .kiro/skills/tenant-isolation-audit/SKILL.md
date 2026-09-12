---
name: tenant-isolation-audit
description: Auditar isolamento multi-tenant, autorização, PII e efeitos assíncronos em rotas, jobs, WebSocket, analytics, exports e providers.
---
# Tenant Isolation & SaaS Security Audit

Use esta skill para revisar uma mudança ou fluxo completo. O isolamento depende da aplicação; não presuma RLS ativo no Postgres.

## Mapa de identidade
Para cada entrada, registre usuário, organization_id, papel, recurso-alvo e ownership: REST, Next server/API route, WebSocket, job, retry, webhook, tracking, import, export, PDF, analytics, cache e provider.

## Checklist
- A autenticação valida assinatura, issuer, audience, expiração e organização ativa?
- Toda leitura e mutação aplica organization_id no ponto de query/service, não apenas na UI?
- Ownership é revalidado depois de enqueue, retry, requeue e processamento assíncrono?
- Jobs não podem ser reivindicados, observados ou cancelados por outra organização?
- A primeira mensagem do WebSocket autentica o token e confirma que o job pertence à organização?
- Analytics, CSV/PDF, busca, contagens, caches e exports não misturam organizações?
- Webhooks e tracking não expõem PII, segredos ou identificadores previsíveis além do necessário?
- Provider usage, quotas, secrets, audit log e outbound actions usam o tenant correto?
- Roles/manager/owner são verificados no backend e ações importantes têm auditoria?
- Opt-out, suppression, bounce e consentimento têm precedência sobre automação de outreach?

## Prova negativa
Use pelo menos duas organizações, usuários com papéis diferentes e IDs que existam somente no outro tenant. Cubra sucesso, vazio, 404/403, concorrência, retry, export, WebSocket e job. Um teste que só confirma o happy path não prova isolamento.

## PII e comportamento
Minimize logs, prompts, fixtures e relatórios; redija contato, token e secret. Preserve `unknown`, `empty`, `failed` e `forbidden` como estados distintos. Não faça sondagem ativa de sites nem teste credenciais externas.

## Saída
Para cada finding: severidade P0-P3, arquivo/linha, entrada, tenant atacante/vítima, mecanismo do vazamento, impacto, teste que reproduz, correção sugerida e risco residual. Não implemente correções durante auditoria sem pedido explícito.
