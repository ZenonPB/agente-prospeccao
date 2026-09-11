---
name: security-compliance
description: Revisar ou implementar segurança e compliance do agente-prospeccao: multi-tenancy, PII, LGPD, opt-out, suppression, e-mail, webhooks, provider privacy, secrets, automação comercial e ações externas.
---
# Security & Compliance

Não substitui aconselhamento jurídico; aplica políticas técnicas do produto.

## Multi-tenancy
Cheque organization_id em reads/writes, jobs, analytics, caches, exports, provider usage, webhooks, activities e logs.

## PII
Minimize armazenamento, logs, exports, prompts e telemetry. Não logue contato completo sem necessidade.

## Secrets
Somente settings/secrets store; nunca hardcode, ecoar, inserir em evidence ou commit.

## Outreach
Opt-out/suppression/bounce têm precedência. ASSISTED não envia externo sem aprovação. SUPERVISED age só dentro de policy explícita. LinkedIn/WhatsApp/telefone permanecem manuais enquanto política/integração oficial não autorizar automação.

## Website intelligence
Somente análise passiva pública. Não sondar, bypass auth, explorar vulnerabilidade, brute force ou acessar dado privado.

## Auditoria
Ação automática importante deve registrar quem/agente, quando, policy, entidade e resultado.
