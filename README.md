<div align="center">

# Prospect.ai

### Inteligência comercial, prospecção B2B e CRM em uma única plataforma

Transforma uma intenção de venda em um fluxo completo: **encontrar empresas, qualificar oportunidades, organizar o trabalho comercial, acompanhar negociações e aprender com os resultados reais**.

[![CI](https://github.com/ZenonPB/agente-prospeccao/actions/workflows/ci.yml/badge.svg)](https://github.com/ZenonPB/agente-prospeccao/actions/workflows/ci.yml)
![Version](https://img.shields.io/badge/version-1.0.0-111827)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Python-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

</div>

---

## Sobre o projeto

O **Prospect.ai** nasceu de um problema real de operação comercial: prospectar clientes envolve muito mais do que montar uma lista de empresas.

É preciso descobrir quem realmente tem perfil para uma oferta, reunir evidências, encontrar decisores, priorizar o esforço do time, registrar contatos, acompanhar follow-ups, entender o funil e aprender com o que de fato virou reunião, proposta ou venda.

A plataforma foi desenvolvida inicialmente para a operação comercial da **AlphaMec**, mas sua arquitetura não é limitada a um único serviço ou segmento. O núcleo trabalha com perfis declarativos de oferta (`OfferProfile`), permitindo representar estratégias comerciais diferentes sem reescrever o motor de prospecção.

Hoje a versão **1.0** reúne prospecção, inteligência comercial, CRM, automação controlada, analytics e aprendizado supervisionado em uma experiência única.

---

## O que o sistema faz

O fluxo principal foi desenhado para ser simples para quem vende:

```text
"Quero vender X para Y"
          ↓
  Descoberta de empresas
          ↓
  Análise + evidências
          ↓
Priorização de oportunidades
          ↓
 Decisor + próxima ação
          ↓
 Carteira / follow-ups
          ↓
    Funil de vendas
          ↓
 Resultados e aprendizado
```

Na prática, a plataforma permite:

- criar campanhas em **linguagem natural**;
- descobrir empresas por múltiplas fontes e providers;
- consolidar empresas e pessoas em entidades canônicas;
- enriquecer dados somente quando há justificativa e orçamento;
- avaliar o encaixe entre empresa e oferta com score explicável;
- identificar oportunidades diferentes dentro da mesma empresa;
- encontrar e validar possíveis decisores;
- sugerir a próxima melhor ação comercial;
- organizar carteira, tarefas, follow-ups e negociações;
- trabalhar leads em Kanban e operações em lote;
- importar histórico comercial de CSV/XLSX com preview e deduplicação;
- acompanhar funil, conversão, performance e coaching comercial;
- registrar outcomes reais e usar esses dados para propor melhorias no modelo;
- testar conexões externas sem expor as chaves configuradas.

---

## Por que este projeto é diferente

### Inteligência comercial baseada em evidência

O sistema não trata ausência de informação como informação negativa.

`UNKNOWN != FALSE`

Dados são classificados de forma explícita entre **fato, inferência e hipótese**, e as decisões podem carregar provenance, confiança e justificativas. Isso torna scores e recomendações mais auditáveis e evita uma falsa sensação de certeza.

### Uma empresa pode ter mais de uma oportunidade

A modelagem separa a empresa do contexto comercial e da oferta.

Uma mesma `Company` pode participar de diferentes campanhas e possuir múltiplas `LeadOpportunity`, cada uma com sua própria oferta, score, evidências, versão de regras e outcome.

Essa separação evita um problema comum em CRMs mais simples: transformar a empresa, o lead e a negociação na mesma entidade.

### Motor genérico por oferta

Em vez de espalhar regras como `if oferta == "landing_page"` pelo código, ICP, sinais, thresholds, buyer persona, enrichment, providers, timing e regras específicas ficam em **OfferProfiles declarativos e versionados**.

Isso permite trabalhar, por exemplo, com landing pages, sistemas web, engenharia mecânica ou troféus/eventos usando o mesmo pipeline.

### Aprendizado com controle humano

O Prospect.ai não altera suas regras de produção silenciosamente.

Resultados e feedbacks podem gerar análises e candidatos de melhoria, mas a publicação passa por replay, comparação, aprovação humana, versionamento e possibilidade de rollback.

```text
outcomes + feedback
        ↓
     análise
        ↓
 replay histórico
        ↓
 proposta de melhoria
        ↓
 aprovação humana
        ↓
 nova versão publicada
```

---

## Principais módulos

| Área | O que entrega |
|---|---|
| **Buscar clientes** | Campanhas, discovery federado, eventos e geração por linguagem natural |
| **Leads qualificados** | Score, evidências, prioridade, oferta aplicável e decisores |
| **Minha carteira** | Visão operacional, filtros, saved views, busca e ações em lote |
| **Follow-ups** | Tarefas, sequências, cadências e próximas ações |
| **Funil de vendas** | Kanban, owners, estágios, atividades e outcomes |
| **Resultados** | Analytics, funil, performance, filtros compartilhados e exportação |
| **Melhorias da IA** | Feedback, calibração, replay e controlled learning |
| **O que vendemos** | Perfis de oferta declarativos e versionados por workspace |
| **Configurações** | Equipe, integrações, quotas, secrets e diagnóstico de providers |

A aplicação também possui um **tutorial interativo e retomável**, pensado para apresentar o sistema inteiro sem exigir conhecimento técnico da arquitetura interna.

---

## Arquitetura

O projeto é um monorepo com frontend, API e domínio/workers separados.

```text
┌─────────────────────────────────────────┐
│              Next.js Web                │
│ React 19 · TypeScript · Tailwind · RQ   │
└──────────────────┬──────────────────────┘
                   │ JWT + workspace
                   ▼
┌─────────────────────────────────────────┐
│               FastAPI API               │
│ Auth · CRM · Campaigns · BI · Search    │
│ 360 · Imports · Jobs · Diagnostics      │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│             PostgreSQL 16               │
│ domínio · auditoria · jobs · snapshots  │
└──────────────────▲──────────────────────┘
                   │
┌──────────────────┴──────────────────────┐
│            Workers / Domain             │
│ discovery · entity resolution           │
│ enrichment · scoring · offer matching   │
│ people discovery · workflows · learning │
└─────────────────────────────────────────┘
```

Estrutura principal:

```text
apps/web/          # aplicação Next.js
services/api/      # API FastAPI e camada de aplicação
services/workers/  # domínio, providers, pipeline e migrations
tests/             # unitários, integração e E2E PostgreSQL
docs/              # arquitetura, decisões e runbooks
```

Mais detalhes em [`docs/architecture.md`](docs/architecture.md).

---

## Stack

| Camada | Tecnologias |
|---|---|
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS 4, TanStack Query, Zustand, Recharts, Leaflet |
| **Backend** | Python, FastAPI, SQLAlchemy, Pydantic, JWT |
| **Workers / IA** | Python, HTTPX, arquitetura de adapters/providers e OfferProfile engine |
| **Banco** | PostgreSQL 16, Alembic |
| **Integrações** | Google Places, Groq, Hunter e adapters de CRM |
| **CRM externo** | Pipedrive, HubSpot e Salesforce |
| **Infra** | Docker / Docker Compose, Render-ready configuration |
| **Qualidade** | Pytest, PostgreSQL real em E2E, ESLint, TypeScript, GitHub Actions |

---

## Engenharia por trás da 1.0

Além das funcionalidades visíveis, o projeto trabalha problemas que aparecem em sistemas reais de produção:

- **multi-tenancy** com isolamento por `organization_id`;
- RBAC e escopo comercial por usuário;
- resolução de identidade de empresas e pessoas;
- deduplicação cross-provider;
- idempotência em operações críticas;
- optimistic locking e controle de concorrência;
- snapshots append-only para rastreabilidade;
- jobs concorrentes com `FOR UPDATE SKIP LOCKED`;
- secrets e quotas por workspace;
- retry, backoff e circuit breaker em providers externos;
- provenance e correlation IDs;
- migrations idempotentes;
- backup e restore exercitados no CI;
- proteção contra acesso cross-tenant;
- automação externa com opt-in e fail-closed;
- testes de invariantes contra PostgreSQL real.

Essa parte é especialmente importante no projeto: o objetivo não foi apenas criar telas de CRM, mas construir uma base coerente para uma operação comercial automatizada e auditável.

---

## Modelo de domínio

```text
Organization
 ├── Membership / User
 ├── Company
 │    ├── CompanyAlias
 │    ├── Person
 │    └── Lead
 │         ├── LeadOpportunity [0..N]
 │         │    └── OpportunitySnapshot
 │         ├── CommercialTask
 │         ├── LeadActivity
 │         ├── SequenceEnrollment
 │         └── CommercialOutcome
 ├── Campaign
 └── OfferProfileVersion
```

Conceitos centrais:

- **Organization** — workspace/tenant;
- **Company** — empresa canônica;
- **Person** — pessoa ou decisor canônico;
- **Lead** — contexto comercial da empresa dentro da operação;
- **LeadOpportunity** — uma oferta específica que pode ser vendida;
- **CommercialOutcome** — resultado comercial real e atribuível;
- **OfferProfileVersion** — versão das regras que definem como uma oferta é prospectada.

---

## Qualidade e CI

A suíte de CI valida o sistema em múltiplas camadas antes de qualquer merge:

```bash
# Backend
python -m compileall -q services/api services/workers
python -m pytest tests -q -W error

# Frontend
cd apps/web
npm ci
npm run lint
npx tsc --noEmit
npm run build
```

Também são executados automaticamente:

- migrations Alembic em PostgreSQL real;
- segunda execução de migration para verificar idempotência;
- verificadores de contrato de schema;
- seed smoke test;
- backup → restore;
- testes de concorrência;
- testes cross-workspace;
- E2E do ciclo comercial;
- invariantes dos módulos de inteligência, CRM, learning e release.

---

## Executando localmente

### Pré-requisitos

- Python compatível com os requirements do projeto;
- Node.js 20+;
- Docker ou PostgreSQL 16;
- chaves externas opcionais para os providers que desejar habilitar.

### 1. Configure o ambiente

```bash
git clone https://github.com/ZenonPB/agente-prospeccao.git
cd agente-prospeccao
cp .env.example .env
```

Preencha apenas as integrações que pretende utilizar. **Nunca versione seu `.env`.**

### 2. Suba o PostgreSQL

```bash
docker compose up -d db
```

### 3. Prepare o banco

```bash
cd services/workers
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m src.seeds.scoring_templates
```

No Windows:

```powershell
.venv\Scripts\activate
```

### 4. Execute a API

```bash
cd services/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 5. Execute o frontend

```bash
cd apps/web
npm ci
npm run dev
```

A aplicação web roda por padrão em `http://localhost:3001` e a API em `http://localhost:8000`.

Para o fluxo completo consulte [`QUICKSTART.md`](QUICKSTART.md). Para deploy, veja [`DEPLOY.md`](DEPLOY.md).

---

## Status

**AlphaMec 1.0 — escopo técnico concluído.**

Os blocos de inteligência de prospecção, CRM operacional, aprendizado controlado, UAT multi-workspace, production readiness e experiência final da 1.0 possuem cobertura automatizada e gates de CI.

O que o repositório **não** tenta fingir é evidência de mercado: métricas como taxa real de resposta, reuniões, propostas, contratos e receita precisam vir de campanhas externas autorizadas e outcomes reais. Teste automatizado não é conversão comercial.

O estado técnico detalhado está em [`docs/00-status-mapa.md`](docs/00-status-mapa.md).

---

## Segurança

Alguns princípios do projeto:

- segredos reais nunca devem ser commitados;
- providers externos são habilitados por opt-in e quota;
- dados são sempre filtrados pelo workspace no backend;
- operações sensíveis respeitam RBAC;
- logs devem evitar PII e secrets;
- suppression/opt-out fazem parte do fluxo de outreach;
- o diagnóstico de providers nunca devolve a chave nem o corpo bruto da resposta externa;
- ações automáticas de produção devem ser explicitamente autorizadas.

---

## Documentação

A pasta [`docs/`](docs/) contém a documentação técnica e operacional do projeto.

Pontos de entrada recomendados:

- [`docs/00-status-mapa.md`](docs/00-status-mapa.md) — estado real das capabilities;
- [`docs/architecture.md`](docs/architecture.md) — arquitetura e domínio;
- [`docs/roadmap.md`](docs/roadmap.md) — evolução do produto;
- [`QUICKSTART.md`](QUICKSTART.md) — execução local;
- [`DEPLOY.md`](DEPLOY.md) — preparação para deploy.

---

## Sobre este repositório

Este projeto também faz parte do meu portfólio de desenvolvimento de software.

Ele reúne temas que considero especialmente importantes em aplicações modernas: **backend e frontend integrados, modelagem de domínio, sistemas multi-tenant, automação, IA aplicada a um problema real, integração com serviços externos, segurança, concorrência, observabilidade e testes de produção**.

O foco do Prospect.ai não é usar IA como um recurso visual ou isolado. A proposta é colocá-la dentro de um fluxo de negócio onde suas decisões possam ser explicadas, corrigidas, medidas e melhoradas com dados reais.

Desenvolvido por **[Zenon Parelli Bergamo](https://github.com/ZenonPB)**.

---

## Licença

Distribuído sob a licença MIT. Consulte [`LICENSE`](LICENSE).
