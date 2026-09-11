---
name: implementation-review
description: Auditar uma Task/Spec já implementada contra requisitos, critérios de aceite e Definition of Done. Use após implementação de milestone/Task e antes de declarar COMPLETE ou iniciar a próxima fase.
---
# Implementation Review

Pergunta central: a Task está pronta ou só existe scaffold?

## Processo
Leia Task/Spec; extraia requisitos verificáveis; encontre implementação, consumidor real, persistência, testes e observabilidade; execute validações; compare com aceite.

## Definition of Done
- contrato claro;
- implementação e consumidor reais;
- pipeline/UI quando requerido;
- tenant scope;
- provenance;
- failed/empty/unknown separados;
- retry para IO;
- observabilidade;
- persistência quando requerida;
- unit/integration/E2E quando aplicável;
- docs;
- sem placeholder como sucesso;
- learning não contaminado;
- auditabilidade;
- qualidade mensurável quando aplicável.

Classifique: `COMPLETE`, `COMPLETE_WITH_FOLLOWUPS`, `PARTIAL`, `SCAFFOLD_ONLY`, `BLOCKED`.

Não implemente correções durante auditoria, salvo pedido explícito.
