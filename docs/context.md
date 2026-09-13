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
analytics, feedback, controlled learning, Opportunity 360 read-only.

Em validação no PR #172:
- OfferProfile efetivo por workspace aplicado ao pipeline inteiro;
- Company 360 read-only;
- Person 360 read-only;
- ressincronização documental.

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
domínio e UAT que justifiquem entidade própria.

## Prioridades atuais

1. fechar PR #172 com CI verde;
2. Opportunity 360 editável reutilizando campos/entidades existentes;
3. importador histórico seguro da planilha AlphaMec;
4. Filter Context compartilhado + BI interativo;
5. coaching e calibração com feedback/outcomes;
6. Golden Path troféus/eventos/MEJ;
7. UAT multi-workspace;
8. campanha real autorizada e hardening final.

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
