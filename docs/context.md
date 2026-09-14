# Contexto do projeto

> **LIVE · atualizado em 2026-09-13.** Antes de trabalhar no repositório, leia
> `docs/README.md`, `docs/00-status-mapa.md`, `docs/architecture.md` e
> `docs/roadmap.md`.

## Produto

O Agente de Prospecção é uma plataforma multi-workspace de inteligência
comercial + CRM. O primeiro cliente operacional é a AlphaMec/Empresa Júnior,
mas o núcleo deve permanecer genérico: diferenças entre ofertas pertencem a
`OfferProfile`, não a branches hardcoded no engine.

O objetivo do RC é substituir a planilha comercial e operar o ciclo:

`descobrir → qualificar → identificar decisor → priorizar → agir → acompanhar → fechar/perder → aprender`

## Estado atual

Entregues: data network federada, Company/Person canônicas, entity resolution,
pre-scoring, enrichment, scoring, OfferMatcher, oportunidades versionadas,
decisor/contato, Next Best Action, sequences/workflows/tasks, Kanban, CRM sync,
analytics, feedback, controlled learning, Opportunity 360 read-only,
Company 360, Person 360, OfferProfile efetivo tenant-safe no pipeline inteiro e
Opportunity 360 editável.

A edição operacional da Opportunity 360 está entregue:
- comandos sobre `Lead`/`CommercialTask`, sem estado comercial paralelo;
- RBAC e isolamento para owner/status/estágio/valor/previsão/próxima ação/notas;
- status perdido + motivo validados atomicamente antes de flush;
- criação de tarefa idempotente e segura sob corrida concorrente;
- editor web acessível, semântico e responsivo;
- suíte PostgreSQL específica no gate E2E;
- migration que elimina drift entre o enum de activities do runtime e o PostgreSQL.

A tela de relatórios usa um snapshot comercial único derivado da URL (`period`,
`campaign`, `consultant`, busca, status e score, além das dimensões suportadas),
compartilhado pelas consultas de analytics e pela exportação PDF. O snapshot é
normalizado para query keys determinísticas, restaura navegação/reload e mantém
loading, erro e dados parciais independentes por visão.

O Historical Importer backend e frontend estão integrados em
`apps/web/src/components/campanhas/csv-import-modal.tsx`. O fluxo usa upload,
preview, dry-run, confirmação, processamento assíncrono e relatório de linhas;
o import síncrono de campanha e o webhook permanecem compatibilidade legada e
não são a fonte do novo lifecycle.

B5.1/B5.2 têm filtros server-side e um snapshot comercial compartilhado entre
as consultas de analytics e a exportação PDF. B6 agora tem `GET /api/leads`
aditivo, com cursor estável e compatibilidade offset, além de
`POST /api/leads/bulk/preview` e `POST /api/leads/bulk/execute`. As operações
allowlist são `status` e `assign`, limitadas a 100 registros, no fluxo
preview → confirmação → execute, com resultados `accepted`, `duplicate`,
`rejected` e `failed`. A execução usa `expected_updated_at` fail-closed,
tenant/RBAC e `CommercialBulkOperation` como ledger técnico; a migration
`f2b3c4d5e6f7` faz o backfill/default de `Lead.updated_at`. Bulk status usa a
transição canônica, registra `LeadActivity`/outcome e cancela a cadência em
estados terminais. No frontend, a seleção é limitada, a paginação usa cursor
com React Query, estados parciais são preservados, retry reutiliza a mesma
idempotency key e rejeitados/falhos selecionados não são descartados. A
implementação não declara B6 nem o RC totalmente concluídos: permanecem os
follow-ups de validação PostgreSQL, migration/schema/concorrência/tenant real,
`verify_migrations`, browser/a11y/responsive smoke e export server-side
auditável, bloqueados pela ausência de `E2E_DATABASE_URL`/browser.

## Invariantes que não podem regredir

### Tenant isolation

- toda leitura/escrita sensível é org-scoped;
- UUID conhecido de outro workspace não concede acesso;
- relações também são filtradas por org quando carregam `organization_id`;
- CONSULTOR respeita carteira;
- secrets, quotas, OfferProfiles publicados e providers são separados por org;
- cross-tenant deve ser testado, não presumido.

### OfferProfile

- catálogo base = fallback;
- versão publicada da organização = overlay efetivo;
- pipeline usa a versão efetiva do workspace;
- nenhuma publicação é automática;
- learning gera proposta/evidência e exige aprovação humana;
- rollback deve restaurar snapshot exato.

### Dados e evidência

- `UNKNOWN != FALSE`;
- FACT/INFERENCE/HYPOTHESIS não são confundidos;
- dados externos guardam provenance/confidence/timestamps quando disponíveis;
- nenhuma informação inexistente é fabricada apenas para preencher UI;
- toda venda/outcome deve apontar para a oportunidade correta quando possível.

### CRM

Fontes canônicas:
- Company = conta;
- Person = pessoa/decisor;
- Lead = contexto comercial/campanha;
- LeadOpportunity = oferta que pode ser vendida;
- CommercialTask = tarefa;
- LeadActivity = trilha;
- CommercialOutcome = resultado atribuído.

Não criar tabelas duplicadas de Proposal/Contract/Note até existir regra de
domínio e UAT que justifiquem entidade própria. Edição de Opportunity 360 deve
mutar essas fontes canônicas, não introduzir estado paralelo.

## Historical Importer

O backend agora expõe `/api/imports` para upload seguro CSV/XLSX, preview,
dry-run, confirmação, consulta paginada de resultados, cancelamento e
recovery. A confirmação cria um `ImportJob` tenant-scoped e o consumer
processa lotes de até 1.000 linhas com dedupe conservador, provenance,
idempotência por workspace e estados explícitos. O frontend está integrado em
`apps/web/src/components/campanhas/csv-import-modal.tsx`; o import síncrono de
campanha e o webhook permanecem compatibilidade legada, e não são a fonte do
novo lifecycle.

## Prioridades atuais

1. export server-side auditável, saved views e global CRM bulk;
2. E2E/migration/schema/concorrência/tenant real PostgreSQL para B6;
3. coaching e calibração com feedback/outcomes;
4. Golden Path troféus/eventos/MEJ;
5. UAT multi-workspace;
6. campanha real autorizada e hardening final.

## Convenções de implementação

- branch curta a partir da main;
- PR pequeno o suficiente para revisão, mas vertical e completo;
- primeiro inventariar o que existe; evitar nova entidade sem necessidade;
- backend: segurança, índices/query-count, idempotência, fail-closed;
- frontend: UI comercial, acessibilidade, semântica, estados de loading/error/
  empty, React Query e desempenho;
- APIs não devem gerar N+1;
- jobs longos ficam fora do request;
- providers externos seguem quota/opt-in.

## Gates

Uma entrega só é concluída se o **mesmo HEAD** passar:
- compileall;
- pytest completo com `-W error`;
- migrations PostgreSQL/idempotência/schema verifier;
- E2E/invariantes relevantes;
- web lint + TypeScript + production build;
- documentação LIVE atualizada.

Falha pré-existente não é justificativa para normalizar suíte vermelha. Ou é
corrigida, ou se prova por que o gate oficial a isola corretamente.

Os gates locais atuais passaram: pytest completo (`1458 passed`, `53 skipped`),
compileall, lint, `tsc`, build e diff check. Os skips são dependentes de
PostgreSQL. Permanecem como follow-ups bloqueados pela ausência de
`E2E_DATABASE_URL`/browser: E2E/migration/schema/concorrência/tenant real
PostgreSQL, `verify_migrations` contra banco, browser/a11y/responsive smoke e
export server-side auditável.
