# Fase 2 — Company Search e People Search

## Objetivo

Transformar as entidades canônicas já existentes (`Company` e `Person`) em uma camada de pesquisa comercial reutilizável, sem acoplar a busca ao pipeline de discovery/enrichment e sem introduzir chamadas externas ocultas.

## Contratos entregues

- `POST /api/search/companies`: pesquisa somente empresas pertencentes ao workspace ativo.
- `POST /api/search/people`: pesquisa somente pessoas pertencentes ao workspace ativo e ordena por acionabilidade.
- `POST /api/search/interpret`: usa IA exclusivamente para traduzir linguagem natural em `SearchIntent` validado. O endpoint **não executa a busca** e não chama providers de discovery.
- UI `/buscar`: interpretação assistida, revisão humana dos filtros e execução explícita.

## Semântica de filtros

A busca avançada usa lógica ternária:

- `MATCH`: há evidência suficiente de que o critério é atendido;
- `NO_MATCH`: há evidência suficiente de que o critério não é atendido;
- `UNKNOWN`: o dado necessário não existe ou não é confiável o bastante para afirmar.

`UNKNOWN` nunca é convertido silenciosamente em fato negativo. Em Company Search ele é excluído por padrão e pode ser incluído explicitamente com `include_unknown=true`, ficando identificado na resposta e na UI.

A expressão avançada aceita apenas campos e operadores de allowlist. AND/OR/NOT são avaliados sem gerar SQL arbitrário e a profundidade é limitada para evitar abuso de payload.

## ActionableContactScore

O score 0–100 é determinístico, sem I/O, e combina:

- confiança de identidade (25%);
- aderência ao papel (20%);
- confiança de e-mail (20%);
- confiança de telefone (10%);
- atualidade da verificação (10%);
- acionabilidade/roteabilidade (15%).

O breakdown preserva `known`/`unknown`, a fonte de cada dimensão e `coverage`. Portanto, a ordenação é conservadora sem esconder lacunas de dados.

## Performance e escalabilidade

A fase usa as entidades canônicas já consolidadas e faz leituras em lote para CompanyRecord, Enrichment e LeadOpportunity, evitando N+1. A varredura heterogênea em JSON/sinais é limitada a 2.000 candidatos por request e informa `candidate_scan_truncated=true` quando o usuário precisa refinar a consulta.

Esse limite é deliberado: a próxima evolução de escala pode materializar um índice/documento de busca ou adotar PostgreSQL FTS/GIN sem alterar o contrato HTTP nem a UI.

## Segurança

- `organization_id` é aplicado na primeira consulta de `Company`, `Person`, `Lead` e `LeadOpportunity`;
- a API continua exigindo autenticação e membership do workspace ativo;
- a DSL não aceita nome de coluna/SQL arbitrário;
- interpretação por IA passa pela quota e secret BYOK já existentes;
- o JSON da LLM é validado por Pydantic antes de chegar à UI;
- providers externos não são disparados por nenhum endpoint de busca.

## Gate de release

A fase só pode entrar em `main` quando o mesmo HEAD do PR comprovar: suíte backend com warnings como erro, migrations idempotentes + schema contract, E2E em PostgreSQL real, invariante de concorrência, lint, TypeScript e build de produção do Next.js. UAT com providers/LLM reais é registrado separadamente e nunca é substituído por mocks.

## Limites intencionais

A busca consulta dados já conhecidos. Encontrar empresas ou decisores novos continua responsabilidade do pipeline/provider waterfall. Saved Searches, AccountWatch, TAM, Data Health avançado e integrações externas permanecem fora desta fase.
