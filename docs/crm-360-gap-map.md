# CRM 360 — gap map

> **LIVE · atualizado em 2026-09-14.** Opportunity 360 read-only, Company 360 e
> Person 360 read-only estão entregues. A edição operacional da Opportunity 360
> também está entregue. O Historical Importer backend + frontend está integrado,
> e o bulk de leads B6 foi implementado sem encerrar ainda todas as provas de
> produção PostgreSQL e browser.

## Modelo canônico reutilizado

| Necessidade | Fonte atual |
|---|---|
| Conta/empresa | `Company` + `CompanyAlias` |
| Pessoa/decisor | `Person` (+ `Contact` legado quando necessário) |
| Contexto comercial | `Lead` |
| Oferta/oportunidade | `LeadOpportunityRow` + snapshots |
| Owner/status/valor/previsão | `Lead` |
| Atividades | `LeadActivity` |
| Tarefas | `CommercialTask` |
| Cadência | `SequenceEnrollment` / `SequenceExecution` |
| Automação | `WorkflowRun` |
| Feedback | `LeadUsefulnessFeedback` / `ScoringFeedback` |
| Resultado | `CommercialOutcomeRow` / `Conversion` |
| Próxima ação | `NextBestActionDecision` + campos de Lead |

## Historical Importer

O fluxo backend e frontend está integrado em
`apps/web/src/components/campanhas/csv-import-modal.tsx`, com upload
CSV/XLSX, preview, dry-run, confirmação, processamento assíncrono e relatório
de linhas. O novo lifecycle mantém Company/Person/Lead/Contact e
CompanyAlias canônicos, dedupe conservador, provenance, idempotência e estados
explícitos; import síncrono de campanha e webhook permanecem compatibilidade
legada.

## Opportunity 360

### Leitura entregue

- lookup `(opportunity_id, organization_id)` fail-closed;
- Company + decisor/contatos;
- oferta/versão, score, breakdown, sinais/evidências;
- qualificação/intent/timing quando persistidos;
- owner, status, estágio, valor, previsão e próxima ação;
- tarefas, atividades, feedback, outcomes;
- sequences/workflows;
- timeline normalizada e determinística;
- UI comercial com estados loading/error/empty;
- testes PostgreSQL de cross-tenant e query-count.

### Edição operacional

Entregue:

- `PATCH /api/opportunities/{id}/360` atualiza a fonte canônica (`Lead`) para
  owner, status, estágio, valor, previsão, próxima ação, motivo de perda e notas;
- `POST /api/opportunities/{id}/tasks` cria `CommercialTask` idempotente;
- `PATCH /api/opportunities/{id}/tasks/{task_id}` atualiza tarefa existente;
- ANALYST continua read-only; CONSULTOR só opera a própria carteira e não
  atribui recursos a colegas; MANAGER/OWNER/ADMIN podem administrar ownership;
- owner/tarefa só aceitam membros do workspace;
- status `PERDIDO` exige motivo e o par status/motivo é validado atomicamente
  antes de qualquer flush, preservando a constraint do banco;
- tarefas usam `UNIQUE(organization_id, idempotency_key)` como autoridade de
  idempotência e tratam corrida concorrente com rollback + leitura do vencedor;
- migration alinha o enum PostgreSQL `lead_activity_action` ao runtime para
  `NEGOTIATION_UPDATED`, eliminando drift que só aparecia em banco real;
- editor web dedicado em `/oportunidades/360/[id]/editar`, com controles
  semânticos nativos, navegação por teclado, layout responsivo, estados de
  loading/error/read-only, feedback por toast e mutations via React Query;
- atualização de tarefa usa optimistic update com rollback;
- suíte PostgreSQL cobre RBAC, cross-tenant/carteira, idempotência, validação e
  relação tarefa↔lead e roda explicitamente no CI.

### Gap restante

- export server-side auditável;
- saved views, global search e ações em massa globais integradas ao CRM;
- decidir via UAT se `Lead.notes` basta ou se notas precisam entidade
  append-only própria;
- propostas/contratos só devem virar entidades quando houver ciclo de vida real;
- UAT multi-workspace.

### Bulk de leads — B6

Entregue no backend e frontend:

- `GET /api/leads` aditivo, com cursor estável e compatibilidade offset;
- `POST /api/leads/bulk/preview` e `POST /api/leads/bulk/execute`;
- operações allowlist `status` e `assign`, máximo de 100 registros e fluxo
  preview → confirmação → execute;
- resultados `accepted`, `duplicate`, `rejected` e `failed`;
- `expected_updated_at` fail-closed, tenant/RBAC e `CommercialBulkOperation`
  como ledger técnico;
- migration `f2b3c4d5e6f7` para backfill/default de `Lead.updated_at`;
- bulk status com transição canônica, `LeadActivity`/outcome e cancelamento de
  cadência em estados terminais;
- frontend com cursor React Query, seleção limitada, estados parciais, retry
  com a mesma idempotency key e preservação de rejeitados/falhos selecionados.

B6 está fechado no escopo técnico do RC: o CI aplica migrations em PostgreSQL real,
executa schema verifier e cobre concorrência/idempotência do bulk em banco real. Smoke
manual de browser continua parte do UAT, não uma lacuna de consistência do domínio.

## Company 360

### Entregue

- dados canônicos de Company;
- aliases/origens;
- pessoas vinculadas;
- leads/contextos comerciais visíveis;
- oportunidades, tarefas e outcomes;
- receita ganha e melhores scores;
- timeline derivada de fontes existentes;
- carteira do CONSULTOR respeitada;
- gestores podem consultar Company canônica mesmo sem lead vinculado;
- UI em `/crm/empresas/[companyId]`.

### Gap

- edição canônica de dados permitidos;
- merge/revisão manual de aliases/duplicatas;
- tags/segmentação operacional;
- visão de propostas/contratos apenas quando o domínio existir;
- bulk actions e global search conectados.

## Person 360

### Entregue

- Person canônica + confiança/verificação/roteabilidade;
- Company relacionada;
- leads e oportunidades visíveis;
- tarefas/outcomes/timeline;
- UI em `/crm/pessoas/[personId]`.

### Gap

- edição/validação humana de identidade;
- histórico canônico de mudanças de emprego se necessário no CRM;
- ações de contato integradas à tela sem duplicar cadência;
- merge de pessoas duplicadas com auditoria.

## Proposal / Contract / Note

Ainda **não** existem entidades canônicas completas para esses conceitos. Não
serão criadas só para completar a aparência da tela 360. Até o UAT provar
necessidade:

- proposta enviada continua representada por status/atividade/cadência;
- contrato/outcome continua nos campos comerciais existentes e outcomes;
- nota operacional simples continua em `Lead.notes`.

Quando o fluxo AlphaMec demonstrar ciclo de vida próprio (versões, arquivos,
aprovação, assinatura, auditoria), então novas entidades podem ser propostas.

## Critério de conclusão do CRM para AlphaMec RC

A planilha deixa de ser fonte operacional quando o sistema permite, com UAT:

1. encontrar conta/pessoa/oportunidade;
2. atribuir owner;
3. mover estágio;
4. registrar valor/previsão/motivo de perda;
5. planejar e concluir tarefa/próxima ação;
6. consultar timeline e contexto 360;
7. importar histórico com dedupe/auditoria;
8. filtrar/exportar e operar em massa;
9. medir pipeline/resultados no BI;
10. provar isolamento entre workspaces.
