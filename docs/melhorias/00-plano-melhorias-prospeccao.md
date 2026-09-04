# Plano de melhorias — Agente de Prospecção

> **Status geral: 🟡 Especificação proposta.**
> Este pacote transforma as recomendações das análises recentes em documentos unitários de implementação, no formato de `docs/` do repositório.

## Objetivo

Evoluir o projeto para uma plataforma de prospecção B2B genérica, explicável e eficiente, excepcional em Landing Pages, sistemas web/ERP e Engenharia Mecânica, sem acoplar o motor central a regras específicas de cada vertical.

## Princípios

- O engine é genérico; a vertical fornece políticas e sinais.
- Descobrir muitos candidatos, ranquear barato e enriquecer seletivamente.
- Separar fatos, inferências, hipóteses e desconhecidos.
- Separar fit, necessidade, intenção, poder de compra e alcançabilidade.
- Resolver a identidade do decisor antes de gastar créditos procurando contato.
- Aprender com outcomes comerciais, não apenas com opinião sobre score.

## Ordem macro recomendada

1. Fundação: `ProspectingProfile`, `Signal Registry`, `Candidate` e score vetorial.
2. Retrieval: multi-query, query generation, Discovery Planner e CNAE provider.
3. Eficiência: pre-score e enrichment por custo/vertical.
4. Diferenciação: Intent Engine, Buying Triggers e Prospecting Hypothesis.
5. Contatos: Company Identity → Buyer Roles → People Discovery → verification.
6. Learning/BI: outcomes, niche priors, Precision@K e actionable_contact_rate.

## Descoberta, pré-ranking e qualidade

- [`01-candidate-pre-scoring-FEITO.md`](./01-candidate-pre-scoring-FEITO.md) — ✅ FEITO — Candidate Pre-Scoring antes do enriquecimento pesado
- [`02-opportunity-score-vector.md`](./02-opportunity-score-vector.md) — Separar oportunidade em múltiplas dimensões de score
- [`03-template-landing-pages.md`](./03-template-landing-pages.md) — Template específico para Landing Pages
- [`04-places-multi-query.md`](./04-places-multi-query.md) — Google Places com busca multi-query
- [`05-search-query-generation.md`](./05-search-query-generation.md) — Geração automática de queries de descoberta
- [`06-candidate-vs-lead-FEITO.md`](./06-candidate-vs-lead-FEITO.md) — ✅ FEITO — Separar Candidate de Lead
- [`07-budgeted-enrichment-FEITO.md`](./07-budgeted-enrichment-FEITO.md) — ✅ FEITO — Enriquecimento seletivo por custo e valor esperado
- [`08-enrichment-order-by-service.md`](./08-enrichment-order-by-service.md) — Ordem de enriquecimento definida pela oferta
- [`09-rating-count-by-vertical.md`](./09-rating-count-by-vertical.md) — Interpretar volume de avaliações por vertical
- [`10-niche-prior-learning.md`](./10-niche-prior-learning.md) — Niche Prior por serviço e organização
- [`11-learning-from-sales-outcomes.md`](./11-learning-from-sales-outcomes.md) — Aprendizado por outcomes comerciais
- [`12-precision-at-k.md`](./12-precision-at-k.md) — Métricas Precision@K para qualidade do ranking
- [`13-chain-detection.md`](./13-chain-detection.md) — Detecção de franquias, redes e empresas independentes
- [`14-decision-maker-accessibility.md`](./14-decision-maker-accessibility.md) — Acessibilidade do decisor como sinal de ranking
- [`15-golden-lead-patterns.md`](./15-golden-lead-patterns.md) — Padrões de Golden Lead por vertical
- [`16-why-prospect-card.md`](./16-why-prospect-card.md) — Mostrar 'por que prospectar' diretamente no card

## Arquitetura universal e inteligência por vertical

- [`17-prospecting-profile-FEITO.md`](./17-prospecting-profile-FEITO.md) — ✅ FEITO — ProspectingProfile como contrato universal de prospecção
- [`18-universal-prospecting-questions.md`](./18-universal-prospecting-questions.md) — Seis perguntas universais do agente de prospecção
- [`19-icp-vs-intent.md`](./19-icp-vs-intent.md) — Separar ICP Fit de Intent
- [`20-signal-registry.md`](./20-signal-registry.md) — Signal Registry universal
- [`21-enrichment-capability-registry.md`](./21-enrichment-capability-registry.md) — Catálogo de capabilities de enriquecimento
- [`22-discovery-planner.md`](./22-discovery-planner.md) — Discovery Planner orientado pela oferta
- [`23-cnae-as-discovery-provider.md`](./23-cnae-as-discovery-provider.md) — CNAE/CNPJ como provider de discovery para B2B industrial
- [`24-intent-engine.md`](./24-intent-engine.md) — Intent Engine para sinais de compra
- [`25-decision-maker-strategy-by-vertical.md`](./25-decision-maker-strategy-by-vertical.md) — Decision Maker Strategy por vertical
- [`26-buying-trigger.md`](./26-buying-trigger.md) — Buying Trigger e Why Now
- [`27-opportunity-vector-v2.md`](./27-opportunity-vector-v2.md) — Opportunity Score como vetor universal
- [`28-prospecting-hypothesis.md`](./28-prospecting-hypothesis.md) — Prospecting Hypothesis por lead
- [`29-epistemic-status.md`](./29-epistemic-status.md) — Status epistêmico para fatos, inferências e hipóteses
- [`30-discovery-questions.md`](./30-discovery-questions.md) — Perguntas de qualificação definidas pela vertical
- [`31-vertical-pack.md`](./31-vertical-pack.md) — Vertical Pack declarativo
- [`32-archetypes-as-fallback.md`](./32-archetypes-as-fallback.md) — Archetypes apenas como fallback de geração
- [`33-three-level-learning.md`](./33-three-level-learning.md) — Aprendizado em três níveis: global, vertical e organização

## Decisores e contatos

- [`34-decision-maker-resolution-pipeline.md`](./34-decision-maker-resolution-pipeline.md) — Decision Maker Resolution Pipeline
- [`35-people-discovery-service.md`](./35-people-discovery-service.md) — PeopleDiscoveryService com providers múltiplos
- [`36-qsa-decision-makers.md`](./36-qsa-decision-makers.md) — QSA como fonte de sócios e decisores econômicos
- [`37-person-database-provider.md`](./37-person-database-provider.md) — Provider de base de pessoas por domínio e cargo
- [`38-email-finder-after-identity.md`](./38-email-finder-after-identity.md) — Email Finder somente após resolução de identidade
- [`39-email-pattern-inference.md`](./39-email-pattern-inference.md) — Inferência de padrão de email com verificação obrigatória
- [`40-contact-confidence-score.md`](./40-contact-confidence-score.md) — ContactConfidenceScore e IdentityConfidence
- [`41-channel-priority-by-vertical.md`](./41-channel-priority-by-vertical.md) — Prioridade de canal por vertical
- [`42-routable-contact.md`](./42-routable-contact.md) — Contato direto vs contato roteável
- [`43-multiple-buyers.md`](./43-multiple-buyers.md) — Múltiplos decisores e Buyer Roles
- [`44-cascade-contact-search.md`](./44-cascade-contact-search.md) — Busca em cascata para decisores e contatos
- [`45-company-identity-resolver.md`](./45-company-identity-resolver.md) — CompanyIdentityResolver e aliases da empresa
- [`46-domain-first-person-search.md`](./46-domain-first-person-search.md) — Buscar pessoas por domínio antes de localização
- [`47-actionable-contact-rate.md`](./47-actionable-contact-rate.md) — Actionable Contact Rate como métrica principal de contato

## Regra de execução para agentes

Os documentos são especificações de mudança, não prova de que a implementação já existe. Antes de alterar código, o agente deve ler `docs/context.md`, `docs/architecture.md`, `docs/business-rules.md`, `docs/decisions.md` e os arquivos atuais envolvidos; depois deve confirmar modelos, migrations, rotas, contratos e testes existentes. Se a implementação atual já cobrir parte do documento, adaptar a solução em vez de duplicar serviços.
