# Contrato operacional — Fase 1H

Este arquivo marca o ponto de partida do bloco de People & Contact Intelligence e registra os invariantes que devem permanecer verdadeiros durante sua implementação.

## Base validada

O bloco parte da `main` após o merge da Fase 1H. Antes da abertura desta branch, o SHA de `main` foi validado pelo CI pós-merge nos quatro gates oficiais: backend, E2E com PostgreSQL real, migrations e web build.

A Fase 1H permanece deliberadamente observacional: o diagnóstico de piloto não altera score, ranking, status ou CRM e não executa providers externos. `ready_for_review` significa somente suficiência para revisão humana; `promotion_allowed` continua falso.

## Invariantes para o próximo bloco

1. O fluxo existente de produção continua autoridade até que uma mudança seja explicitamente promovida.
2. `UNKNOWN` nunca é convertido silenciosamente em `FALSE`, zero ou ausência de interesse.
3. Falha, provider desabilitado, quota esgotada, ausência de resultado e resultado insuficiente são estados distintos e observáveis.
4. Nenhuma chamada paga é obrigatória para o caminho principal e nenhuma despesa pode ocorrer silenciosamente.
5. Toda persistência e leitura comercial permanece limitada à organização ativa.
6. People & Contact Intelligence deve estender `PeopleProviderRegistry`, `ContactEnrichmentService`, providers existentes, quota, secrets, telemetria, provenance e entity resolution; não será criado um segundo sistema paralelo.
7. A cascata deve priorizar fontes gratuitas e já conhecidas antes de Hunter ou futuros providers pagos.
8. Contatabilidade mede a capacidade de chegar à pessoa adequada; ela não reduz artificialmente uma empresa de alta aderência a uma oportunidade medíocre.
9. Erros em fronteiras externas devem produzir estado/diagnóstico acionável, sem expor segredo, payload sensível ou PII desnecessária.
10. O merge deste bloco exige CI oficial verde no HEAD exato da PR e revisão dos invariantes de compatibilidade.

## Critério de regressão da Fase 1H

Qualquer mudança deste bloco que faça o endpoint de pilot readiness executar I/O externo, alterar ranking, promover shadow automaticamente, perder isolamento por organização ou confundir UNKNOWN com zero é regressão bloqueadora.
