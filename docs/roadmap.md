# Roadmap — AlphaMec Release Candidate

> **LIVE · atualizado em 2026-09-14.** Leia `docs/README.md` antes dos snapshots
> de fases antigas. O estado atual inclui a consolidação do Bloco A de
> Prospecting Intelligence; código/testes prevalecem sobre snapshots antigos.

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
- Historical Importer com contexto comercial e gate PostgreSQL;
- Filter Context compartilhado + BI no escopo RC;
- OfferProfile efetivo por workspace em todo o pipeline;
- Prospecting Intelligence com quality gates e política `UNKNOWN != FALSE`;
- Golden Paths para landing pages, sistemas web, engenharia e troféus;
- Event Intelligence declarativa para eventos gerais, esportivos e MEJ;
- timing comercial e persistência idempotente de oportunidades de evento;
- benchmark sintético de regressão como quality gate;
- criação de campanha natural-language-first sem exigir jargão técnico;
- CI com backend `-W error`, migrations PostgreSQL, E2E crítico e web build.

## Bloco A — Prospecting Intelligence + Golden Paths — ✅ técnico

Objetivo cumprido no código e nos gates automatizados:

- diferenças de oferta ficam em `OfferProfile`/configuração de portfólio;
- Event Intelligence recebe regras declarativas em vez de conhecer MEJ/esporte no core;
- MEJ e esporte roteiam para ofertas específicas sem criar entidades paralelas;
- contexto derivado é `INFERENCE`, ausência permanece `UNKNOWN`;
- quantidade estimada de premiações só é calculada a partir de campos estruturados e continua inferência;
- timing evita tratar evento imediato como oportunidade perfeita e reconhece janela ideal de venda/execução;
- matching de evento é idempotente e mantém provenance/evidence;
- benchmark verifica roteamento, cobertura de evidência, recall de alta confiança e hard negatives;
- ratchet de genericidade impede reintrodução de conhecimento de domínio no core;
- Event Intelligence/Golden Paths possuem gate explícito em PostgreSQL real;
- frontend de nova campanha passou a partir do objetivo comercial, sem expor provider/query/template/profile ao usuário comum.

**Limite:** o benchmark é sintético. Este bloco não declara `precision@20`,
conversão, reuniões ou receita reais. Esses indicadores só entram como evidência
quando campanhas autorizadas gerarem outcomes reais atribuídos.

## Próximas entregas para o RC

### 1. CRM como sistema operacional de vendas

Completar a experiência necessária para abandonar a planilha: fila diária do
consultor, busca/visões salvas quando justificadas pelo fluxo, ações em massa
seguras e superfícies 360 editáveis onde ainda forem read-only. Não criar
Proposal/Contract/Note paralelos sem regra de domínio real.

### 2. BI de gestão / cross-filter

Evoluir o BI já server-side para interação estilo Power BI: seleção visual que
compõe filtros entre gráficos/tabelas, comparação de períodos, aging, tempo por
estágio, motivos de perda, SLA de follow-up e visão de qualidade de prospecção.

### 3. Feedback, coaching e calibração

Consolidar feedback, score feedback e outcomes em coaching útil ao vendedor e à
gestão. Learning continua controlado: proposta → evidência → aprovação humana →
publicação versionada → rollback. Nunca aplicar mudança de produção
silenciosamente.

### 4. UAT multi-workspace

Cenários mínimos:
- A não lê/escreve B por UUID conhecido;
- overlays OfferProfile distintos não contaminam jobs concorrentes;
- providers/secrets/quotas separados;
- CRM e dashboards respeitam carteira e organização;
- importador nunca resolve entidades fora do workspace;
- usuário membro de dois ou mais workspaces alterna contexto sem mistura de cache, jobs ou analytics.

### 5. Campanhas reais e hardening final

Rodar campanhas AlphaMec autorizadas para landing pages, sistemas, engenharia,
troféus gerais/esportivos e MEJ. Medir coverage, `precision@10/20`, contatos e
decisores válidos, resposta, reunião, proposta, contrato, custo, latência e
problemas de UX. Achados são classificados em `BLOCKS_ALPHAMEC`,
`IMPORTANT_ALPHAMEC` ou `DEFER_TO_V2`.

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
7. para Bloco A, Event Intelligence/Golden Paths persistentes em PostgreSQL real;
8. `npm ci`, lint, `tsc --noEmit` e production build;
9. documentação LIVE atualizada;
10. todos os checks verdes no **mesmo HEAD** que será mergeado.
