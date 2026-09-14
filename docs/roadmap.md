# Roadmap — AlphaMec Release Candidate

> **LIVE · atualizado em 2026-09-14.** Leia `docs/README.md` antes dos snapshots
> de fases antigas. Estado base após PR #173: Opportunity 360 operacionalmente
> editável, preservando as fontes canônicas do CRM.

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
- Kanban comercial;
- Opportunity 360 read-only e editável;
- Company 360 e Person 360;
- OfferProfile efetivo por workspace em todo o pipeline;
- CI com backend `-W error`, migrations PostgreSQL, E2E crítico e web build.

## Batch 3 — Opportunity 360 editável — ✅

Objetivo cumprido: operar a oportunidade sem criar uma segunda fonte de verdade.

Entregue:

- `OpportunityCommandService` sobre `LeadOpportunityRow`, `Lead` e
  `CommercialTask` existentes;
- edição de owner, status, estágio, valor, previsão, próxima ação, motivo de
  perda e notas;
- validação atômica de status/motivo de perda para respeitar constraints do DB;
- criação idempotente de tarefas protegida também contra requests concorrentes
  pela UNIQUE do PostgreSQL + recuperação do vencedor da corrida;
- atualização de tarefas existentes;
- ANALYST read-only; CONSULTOR restrito à própria carteira; MANAGER/OWNER/ADMIN
  com gestão de ownership;
- validação de membership no workspace e lookup fail-closed;
- editor web em `/oportunidades/360/[id]/editar` com controles semânticos,
  navegação por teclado, feedback de operação e mutations/cache via React Query;
- optimistic update com rollback para conclusão/dispensa de tarefa;
- migration idempotente que alinha `LeadActivityAction.NEGOTIATION_UPDATED` ao
  enum PostgreSQL;
- suíte PostgreSQL de permissões, idempotência, validação e relações;
- gate explícito da suíte no job E2E do CI.

O batch foi submetido aos mesmos gates de merge do projeto; todos devem estar
verdes no HEAD final que inclui esta documentação antes do merge.

## Próximas entregas para o RC

### 1. Importador histórico AlphaMec — concluído

Fluxo obrigatório:

`upload → preview → mapping de colunas → validação → dedupe → import → relatório`

Requisitos: dry-run, org-scope, idempotência, erro por linha, nenhuma escrita
parcial silenciosa e auditoria da origem.

### 2. CRM para substituir a planilha

Completar:
Company 360/Person 360 editáveis quando necessário, busca global, filtros,
tags, ações em massa, ownership, tarefas, notas canônicas, propostas/contratos
**somente quando houver modelo de domínio real**, exportação e auditoria.

### 3. Filter Context + BI interativo — concluído no escopo RC

Um contrato de filtro compartilhado por dashboards e tabelas: período,
workspace, owner, campanha, oferta/versão, estágio, segmento, região e provider.
Filtros devem compor queries no backend; não carregar universo inteiro para
filtrar no navegador.

### 4. Feedback, coaching e calibração

Consolidar feedback de utilidade, score feedback e outcomes em análises úteis ao
vendedor e à gestão. Learning continua controlado: proposta → evidência →
aprovação humana → publicação versionada → rollback. Nunca aplicar mudança de
produção silenciosamente.

### 5. Golden Path AlphaMec

Prioridade funcional: troféus/eventos/MEJ, sem hardcode do núcleo. Provar:
discovery → empresa → decisor → oportunidade → ação → contato → outcome → BI.

### 6. UAT multi-workspace

Cenários mínimos:
- A não lê/escreve B por UUID conhecido;
- overlays OfferProfile distintos não contaminam jobs concorrentes;
- providers/secrets/quotas separados;
- CRM e dashboards respeitam carteira e organização;
- importador nunca resolve entidades fora do workspace.

### 7. Campanha real e hardening final

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
