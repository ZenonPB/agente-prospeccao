---
name: ux-review
description: Auditar UX/UI existente no apps/web sem começar por refatoração. Use para revisar tela, CRM, dashboards, formulários, busca, tabelas, filtros, navegação e fluxos comerciais.
---
# UX Review

Primeiro diagnostique; só implemente se o pedido incluir implementação.

## Processo
1. Entenda objetivo e usuário.
2. Leia `apps/web/AGENTS.md`.
3. Inspecione implementação real e padrões existentes.
4. Percorra o fluxo completo, inclusive loading/empty/error/partial.
5. Revise responsividade e acessibilidade.

## Severidade
- `CRITICAL`: impede tarefa, causa erro ou ação perigosa.
- `HIGH`: alto atrito/ambiguidade.
- `MEDIUM`: hierarquia/consistência subótima.
- `POLISH`: acabamento.

Cada achado: problema, evidência, impacto, correção e escopo mínimo.

## Checklist
Hierarquia; legibilidade; filtros removíveis/reproduzíveis; feedback; bulk actions; CRM com estágio/responsável/next action/histórico/decisor/oferta/timing; analytics com período/dimensão/amostra/drill-down/atribuição.

Termine com: corrigir agora, próximo incremento, polish.
