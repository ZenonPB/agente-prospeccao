# Contexto do projeto

> **LIVE · atualizado em 2026-09-14.** Antes de trabalhar no repositório, leia
> `docs/README.md`, `docs/00-status-mapa.md`, `docs/architecture.md`,
> `docs/roadmap.md` e `docs/prospecting-intelligence-benchmark.md`.

## Produto

O Agente de Prospecção é uma plataforma multi-workspace de inteligência
comercial + CRM. O primeiro cliente operacional é a AlphaMec/Empresa Júnior,
mas o núcleo permanece genérico: diferenças entre ofertas pertencem a
`OfferProfile` e configurações externas de portfólio, não a branches hardcoded
na engine.

O objetivo do RC é substituir a planilha comercial e operar o ciclo:

`descobrir → qualificar → identificar decisor → priorizar → agir → acompanhar → fechar/perder → aprender`

## Estado atual

Estão entregues e protegidos por testes: data network federada, Company/Person
canônicas, entity resolution, pre-scoring, enrichment, scoring, OfferMatcher,
oportunidades versionadas, decisor/contato, Next Best Action,
sequences/workflows/tasks, Kanban, CRM sync, Historical Importer, analytics,
Filter Context, feedback, controlled learning, Opportunity 360 editável,
Company/Person 360 read-only e OfferProfile efetivo tenant-safe no pipeline.

### Vertentes

No produto, **Vertente** é a estratégia comercial completa de uma oferta. Sua
representação técnica canônica é o `OfferProfile` efetivo do workspace.

- catálogo factory + versão ativa da organização formam a Vertente efetiva;
- equalizações do catálogo factory acontecem antes dos overlays tenant-scoped;
- `CampaignScoringTemplate` permanece apenas como compatibilidade da etapa de
  avaliação, sem competir com o OfferProfile por ICP/discovery/pesos/timing;
- `/api/vertentes` entrega a estratégia efetiva já agregada para a UI;
- `/configuracoes/vertentes` usa essa API e oferece visão simples e avançada da
  mesma configuração;
- critérios de scoring personalizados legados continuam acessíveis em uma área
  avançada separada enquanto a migração permanece gradual;
- campanhas novas selecionam uma Vertente por `offer_profile_key`; o backend
  valida a chave no registry efetivo da organização e deriva o profile de
  análise, impedindo combinações contraditórias;
- o catálogo factory possui gate explícito de maturidade e Golden Paths. A
  AlphaMec prioriza Troféus/MEJ, Troféus esportivos e as ofertas de Engenharia,
  sem deixar Impressão 3D e Laser abaixo do contrato mínimo.

O Bloco A adiciona a camada de Prospecting Intelligence de produção:

- Golden Paths de landing pages, sistemas web sob medida, engenharia mecânica e
  troféus;
- ofertas específicas de troféus para esporte e MEJ;
- quality gates que limitam confiança quando faltam evidências fortes sem
  transformar `UNKNOWN` em `FALSE`;
- sinais negativos só penalizam quando foram observados;
- Event Intelligence dirigida por regras declarativas externas ao core;
- série/recorrência de eventos e timing comercial orientado a janela de
  venda/aprovação/execução;
- contexto e demanda derivados persistidos como `INFERENCE` com provenance;
- benchmark sintético de regressão com anchors e hard negatives;
- criação de campanha natural-language-first, sem exigir que o usuário conheça
  provider, query, template, profile ou outras estruturas internas;
- gate PostgreSQL real para persistência e idempotência dos Golden Paths de
  eventos.

O benchmark do Bloco A é uma proteção de regressão, não evidência de conversão
real. `precision@20`, resposta, reunião, proposta, contrato e receita só podem
ser declarados após campanhas reais com outcomes atribuídos.

## CRM e BI

Opportunity 360 edita as fontes canônicas (`Lead`, `LeadOpportunityRow`,
`CommercialTask`) com RBAC, optimistic concurrency e tarefas idempotentes. Não
há segunda fonte de verdade comercial.

O Historical Importer suporta CSV/XLSX com preview, mapping, dry-run,
confirmação idempotente, processamento e relatório por linha. Contexto
comercial histórico é preservado e o lifecycle possui E2E PostgreSQL.

Filter Context é compartilhado entre URL/API/analytics/export para período,
campanha, consultor, oferta/versão, canal, status, score, outcome, atribuição,
busca, segmento, cidade/UF e estágio de negociação. Os filtros compõem queries
server-side.

## Invariantes que não podem regredir

### Tenant isolation

- toda leitura/escrita sensível é org-scoped;
- UUID conhecido de outro workspace não concede acesso;
- relações também são filtradas por org quando carregam `organization_id`;
- CONSULTOR respeita carteira;
- secrets, quotas, OfferProfiles publicados e providers são separados por org;
- cross-tenant deve ser testado, não presumido.

### OfferProfile e genericidade

- catálogo base = fallback;
- versão publicada da organização = overlay efetivo;
- pipeline usa a versão efetiva do workspace;
- nenhuma publicação é automática;
- learning gera proposta/evidência e exige aprovação humana;
- rollback restaura snapshot exato;
- core genérico não decide por nomes concretos de oferta/vertical;
- o ratchet de genericidade só pode encolher, nunca acomodar novo acoplamento.

### Dados e evidência

- `UNKNOWN != FALSE`;
- FACT/INFERENCE/HYPOTHESIS não são confundidos;
- dados externos guardam provenance/confidence/timestamps quando disponíveis;
- nenhuma informação inexistente é fabricada para preencher UI;
- inferência de contexto/demanda de evento continua inferência;
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

## Prioridades atuais após o Bloco A

1. CRM operacional para substituir a planilha no uso diário;
2. BI de gestão com cross-filter e análises de funil/aging/SLA;
3. coaching e calibração com feedback/outcomes;
4. UAT multi-workspace formal;
5. campanhas reais autorizadas e hardening final.

## Convenções de implementação

- branch curta a partir da main;
- PR vertical e completo;
- inventariar o que existe antes de criar entidade nova;
- backend: segurança, índices/query-count, idempotência, fail-closed;
- frontend: UI comercial, acessibilidade, semântica, loading/error/empty, React Query e desempenho;
- evitar jargão técnico nas superfícies de vendedor/gestor;
- APIs não devem gerar N+1;
- jobs longos ficam fora do request;
- providers externos seguem quota/opt-in.

## Gates

Uma entrega só é concluída se o **mesmo HEAD** passar:

- `python -m compileall -q services/api services/workers`;
- `python -m pytest tests -q -W error`;
- quality gates específicos do domínio alterado;
- migrations PostgreSQL + segundo upgrade idempotente + schema verifier + seed;
- E2E/invariantes relevantes em PostgreSQL real;
- web lint + TypeScript + production build;
- documentação LIVE atualizada.

Para o Bloco A, o E2E inclui explicitamente Event Intelligence/Golden Paths
persistentes em PostgreSQL. Falha pré-existente não é justificativa para
normalizar suíte vermelha.