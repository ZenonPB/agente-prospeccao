# CRM 360 — gap map

> **LIVE · atualizado em 2026-09-14.** O Bloco B está fechado no escopo técnico:
> Opportunity/Company/Person 360, operação diária, busca, saved views, ações em
> massa, export e BI compartilham as fontes canônicas e o isolamento de tenant.
> UAT formal multi-workspace continua no Bloco D.

## Modelo canônico reutilizado

| Necessidade | Fonte atual |
|---|---|
| Conta/empresa | `Company` + `CompanyAlias` |
| Pessoa/decisor | `Person` (+ `Contact` legado quando necessário) |
| Contexto comercial | `Lead` |
| Oferta/oportunidade | `LeadOpportunityRow` + snapshots |
| Owner/status/valor/previsão | `Lead` |
| Metadados operacionais | `LeadCrmMetadata` 1:1 (tags/arquivamento; não duplica estado comercial) |
| Atividades | `LeadActivity` |
| Tarefas | `CommercialTask` |
| Cadência | `SequenceEnrollment` / `SequenceExecution` |
| Automação | `WorkflowRun` |
| Feedback | `LeadUsefulnessFeedback` / `ScoringFeedback` |
| Resultado | `CommercialOutcomeRow` / `Conversion` |
| Próxima ação | `NextBestActionDecision` + campos de Lead |
| Auditoria de edição CRM | `CrmEntityAudit` |

## Bloco B — Sales Operating System

Entregue de ponta a ponta:

- **Central comercial** em `/crm`, com busca global tenant-safe e fila diária priorizada por tarefas, prazos, estágio, aderência e Next Best Action;
- **carteira operacional** com filtros server-side, seleção e estados de loading/error/empty;
- **saved views** privadas ou compartilhadas no workspace, sem persistir cursores/paginação efêmera;
- **bulk actions** com preview, limite, optimistic concurrency e ledger idempotente para status/owner, estágio, campanha, tags, arquivar/restaurar, iniciar sequência e criar tarefas;
- **export server-side** da seleção com trilha de auditoria;
- **Company 360 editável** em allowlist, protegendo CNPJ como identidade forte, normalizando domínio, com RBAC, carteira, tenant isolation, concorrência otimista e auditoria append-only;
- **Person 360 editável** com identidade forte protegida, edição de contato/cargo/roteabilidade e validação humana explícita sem fabricar confiança;
- **Opportunity 360 editável** permanece a fonte operacional para owner/status/estágio/valor/previsão/próxima ação/motivo de perda/notas e tarefas;
- **BI/Filter Context** server-side, restaurável por URL, saved views e interação entre dimensões comerciais;
- migrations reais, schema verifier e gates PostgreSQL dedicados ao Sales Operating System.

## Historical Importer

O fluxo backend e frontend está integrado em
`apps/web/src/components/campanhas/csv-import-modal.tsx`, com upload CSV/XLSX,
preview, dry-run, confirmação, processamento assíncrono e relatório de linhas.
Mantém Company/Person/Lead/Contact e CompanyAlias canônicos, dedupe conservador,
provenance, idempotência e estados explícitos.

## Opportunity 360

### Entregue

- lookup `(opportunity_id, organization_id)` fail-closed;
- Company + decisor/contatos;
- oferta/versão, score, breakdown, sinais/evidências;
- qualificação/intent/timing quando persistidos;
- owner, status, estágio, valor, previsão e próxima ação;
- tarefas, atividades, feedback, outcomes, sequences/workflows;
- timeline normalizada e determinística;
- comandos canônicos com RBAC/carteira e concorrência;
- criação/edição de tarefas idempotente e race-safe;
- UI comercial e editor dedicado;
- testes PostgreSQL de cross-tenant, query-count, RBAC, idempotência e validação.

## Company 360

### Entregue

- dados canônicos, aliases/origens e pessoas vinculadas;
- leads, oportunidades, tarefas, outcomes, receita e melhores scores;
- timeline derivada das fontes existentes;
- carteira do CONSULTOR respeitada;
- gestores podem consultar Company canônica mesmo sem lead vinculado;
- edição allowlist de dados não-identitários, domínio recalculado quando o site muda;
- optimistic concurrency com `updated_at` e `created_at` como versão inicial de registros legados/recém-criados;
- auditoria append-only de alterações;
- UI em `/crm/empresas/[companyId]`.

### Fora do Bloco B por decisão de domínio

- merge/revisão manual de aliases ou Companies duplicadas só deve ganhar fluxo próprio quando o UAT provar necessidade e regras seguras de merge;
- propostas/contratos só viram entidades quando existir ciclo de vida real próprio.

## Person 360

### Entregue

- Person canônica + confiança/verificação/roteabilidade;
- Company relacionada, leads, oportunidades, tarefas, outcomes e timeline;
- edição humana de nome/cargo/contatos/roteabilidade em allowlist;
- validação humana explícita (`human_verified`) com timestamp e auditoria;
- optimistic concurrency e fail-closed tenant/carteira;
- UI em `/crm/pessoas/[personId]`.

### Fora do Bloco B por decisão de domínio

- histórico formal de mudanças de emprego só será criado se houver lifecycle real no UAT;
- merge de pessoas duplicadas exige política de identidade/auditoria própria antes de ser implementado.

## Proposal / Contract / Note

Ainda **não** existem entidades canônicas completas para esses conceitos, por
decisão deliberada de não criar tabelas para preencher UI:

- proposta enviada continua representada por status/atividade/cadência;
- contrato/outcome continua nos campos comerciais existentes e outcomes;
- nota operacional simples continua em `Lead.notes`.

Quando o fluxo AlphaMec demonstrar ciclo de vida próprio (versões, arquivos,
aprovação, assinatura, auditoria), novas entidades podem ser propostas.

## Critério técnico do Bloco B

No estado atual o sistema oferece, sem depender da planilha como fonte de verdade:

1. encontrar conta/pessoa/lead/oportunidade;
2. atribuir owner e mover status/estágio;
3. registrar valor/previsão/motivo de perda e próxima ação;
4. planejar/concluir tarefas e iniciar sequências;
5. consultar timeline e contexto 360;
6. importar histórico com dedupe/auditoria;
7. salvar/restaurar filtros e operar em massa;
8. etiquetar, arquivar/restaurar e exportar seleções;
9. medir pipeline/resultados no BI com Filter Context compartilhado;
10. aplicar tenant/RBAC/carteira nos comandos e consultas, com gates em PostgreSQL real.

A prova com usuários reais em múltiplos workspaces permanece no **Bloco D — UAT**;
não é tratada como implementação faltante do Bloco B.
