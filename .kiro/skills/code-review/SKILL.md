---
name: code-review
description: Revisar mudanças, diff ou PR do agente-prospeccao procurando bugs, regressões, duplicação arquitetural, segurança, multi-tenancy, qualidade de testes e inconsistências com o domínio. Use antes de merge ou quando pedirem revisão técnica.
---
# Code Review

Entenda objetivo → leia diff → consulte adjacências necessárias → verifique testes/contratos/migrations.

## Severidade
P0: perda/corrupção, vazamento cross-tenant, secret/PII, ação externa não autorizada, migration destrutiva.
P1: bug funcional, learning errado, fonte de verdade duplicada, provider caro indevido, erro virando vazio, retry/idempotência incorretos.
P2: dívida relevante, observabilidade/teste crítico ausente, UX/API inconsistente.
P3: manutenção/polish.

## Domínio
Cheque tenant scope, UNKNOWN, provenance, hardcode de oferta, profile/version reproduzível, provider cost/status/retry, attribution de outcome, policy/opt-out e reuso de modelos existentes.

Saída: achados por severidade com arquivo/trecho, riscos residuais, testes faltantes e conclusão curta.
