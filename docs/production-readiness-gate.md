# Production Readiness Gate — Data Engine Brasil

Este gate impede que `CODE COMPLETE`, `ready_for_review` e validação operacional sejam tratados como sinônimos.

## Estado atual

- código do Data Engine: implementado;
- Commercial Dimensions: shadow por design;
- promoção automática: proibida;
- validação operacional: requer execução controlada com snapshot real e providers autorizados.

## Evidências necessárias

1. CI verde no SHA implantado.
2. Snapshot real do Registry importado e ledger consistente.
3. Busca CNAE/geográfica e fallback exercitados em volume operacional.
4. Três pilotos separados por Vertente conforme `data-engine-brasil-pilot.md`.
5. Budget/quota confirmados, inclusive cenário R$0.
6. Dimensões materializadas sem converter UNKNOWN em zero.
7. People/Contact e provenance revisados em amostra real.
8. Fluxo de conversa exercitado com suppression/opt-out/reply/STOP/bounce.
9. Outcomes usados para promoção somente com atribuição comprovada.
10. Decisão de promoção explícita e reversível; nunca derivada automaticamente do gate.

Enquanto qualquer item depender de evidência externa não executada, o estado permanece `OPERATIONAL VALIDATION REQUIRED`.
