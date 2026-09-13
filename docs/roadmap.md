# Roadmap — AlphaMec Release Candidate

> **LIVE · atualizado em 2026-09-13.** Leia `docs/README.md` antes dos snapshots
> de fases antigas. Estado base: `main` após PR #171; PR #172 em validação.

## Objetivo

Entregar uma plataforma de inteligência comercial e CRM que substitua a
planilha operacional da AlphaMec, mantendo o motor genérico para qualquer
oferta por meio de `OfferProfile` e isolamento estrito por workspace.

## Já entregue e verificado

- multi-workspace e membership/roles;
- Company, Person e Lead/Oportunidade como entidades canônicas;
- identidade cross-provider + aliases/provenance;
- discovery federado, planner, quotas/opt-in e observabilidade;
- pre-scoring, enrichment, scoring e OfferMatcher versionado;
- oportunidades persistidas + snapshots e attribution de outcomes;
- pessoas/decisores, buyer role, verificação e roteabilidade;
- next best action, sequences, workflows e tarefas comerciais;
- CRM adapters/sync/certificação read-only;
- analytics, provider metrics e controlled learning com aprovação/publicação/rollback;
- feedback útil/não útil e score feedback;
- Kanban comercial e Opportunity 360 read-only;
- CI com backend `-W error`, migrations PostgreSQL, E2E crítico e web build.

## Batch em validação — PR #172

### A. OfferProfile efetivo por workspace

O pipeline inteiro deve usar a versão publicada no workspace, não apenas o
catálogo global. Implementação do batch:

- `ContextVar` por job, sem estado global mutável;
- registry efetivo materializado antes de `run_pipeline`;
- consumers legados de `get_default_registry()` recebem o overlay da tarefa;
- construção de outro workspace sempre parte do catálogo base;
- falha de composição = job falha fechado;
- testes de nesting/restauração e concorrência assíncrona.

**DoD:** CI final verde no mesmo HEAD + teste explícito de isolamento.

### B. CRM 360 canônico

- Opportunity 360 read-only: entregue no PR #171;
- Company 360 read-only: implementado no PR #172;
- Person 360 read-only: implementado no PR #172;
- timeline derivada de fontes existentes; nenhuma tabela artificial apenas
  para apresentação;
- escopo de carteira e organization_id aplicados em todas as relações.

**DoD:** PostgreSQL real cobre cross-tenant, dados parciais e query-count.

## Próximas entregas para o RC

### 1. Opportunity 360 editável

Unificar edição comercial sobre fontes já existentes:
owner, estágio/status, valor, previsão, próxima ação, tarefas, notas e motivo de
perda. Não criar segunda representação para campos já presentes em `Lead` ou
`CommercialTask`.

### 2. Importador histórico AlphaMec

Fluxo obrigatório:

`upload → preview → mapping de colunas → validação → dedupe → import → relatório`

Requisitos: dry-run, org-scope, idempotência, erro por linha, nenhuma escrita
parcial silenciosa e auditoria da origem.

### 3. CRM para substituir a planilha

Completar:
Company 360/Person 360 editáveis quando necessário, busca global, filtros,
tags, ações em massa, ownership, tarefas, notas canônicas, propostas/contratos
**somente quando houver modelo de domínio real**, exportação e auditoria.

### 4. Filter Context + BI interativo

Um contrato de filtro compartilhado por dashboards e tabelas: período,
workspace, owner, campanha, oferta/versão, estágio, segmento, região e provider.
Filtros devem compor queries no backend; não carregar universo inteiro para
filtrar no navegador.

### 5. Feedback, coaching e calibração

Consolidar feedback de utilidade, score feedback e outcomes em análises úteis ao
vendedor e à gestão. Learning continua controlado: proposta → evidência →
aprovação humana → publicação versionada → rollback. Nunca aplicar mudança de
produção silenciosamente.

### 6. Golden Path AlphaMec

Prioridade funcional: troféus/eventos/MEJ, sem hardcode do núcleo. Provar:
discovery → empresa → decisor → oportunidade → ação → contato → outcome → BI.

### 7. UAT multi-workspace

Cenários mínimos:
- A não lê/escreve B por UUID conhecido;
- overlays OfferProfile distintos não contaminam jobs concorrentes;
- providers/secrets/quotas separados;
- CRM e dashboards respeitam carteira e organização;
- importador nunca resolve entidades fora do workspace.

### 8. Campanha real e hardening final

Rodar campanha AlphaMec real com credenciais autorizadas; medir coverage,
precision, custo, latência, bounce/routability, conversão e problemas de UX.
Achados são classificados em `BLOCKS_ALPHAMEC`, `IMPORTANT_ALPHAMEC` ou
`DEFER_TO_V2`.

## Depois do RC

- expansão da data network e novos providers;
- learning estatístico mais sofisticado sobre amostras suficientes;
- forecasting/calibração avançados;
- propostas/contratos completos se o UAT comprovar necessidade;
- automações adicionais sem comprometer human-in-the-loop e auditabilidade.

## Gates obrigatórios de merge

1. branch curta a partir da `main` atual;
2. testes do domínio alterado;
3. `python -m compileall -q services/api services/workers`;
4. `python -m pytest tests -q -W error`;
5. migrations em PostgreSQL real + idempotência + schema verifier;
6. E2E crítico e invariantes tenant-safe relevantes;
7. `npm ci`, lint, `tsc --noEmit` e production build;
8. documentação LIVE atualizada;
9. todos os checks verdes no **mesmo HEAD** que será mergeado.
