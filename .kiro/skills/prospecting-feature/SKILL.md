---
name: prospecting-feature
description: Implementar features de domínio da plataforma de prospecção B2B: OfferProfile, discovery, enrichment, signals, intent, scoring, OfferMatcher, People/BuyerPersona, decision makers, opportunities, CRM, Next Best Action, events e learning.
---
# Prospecting Feature

Norte: core genérico + OfferProfile configurável + providers plugáveis + evidence/provenance + outcomes como verdade comercial.

Antes de criar, procure `OfferProfile`, resolver/validator, `OfferMatcher`, `DiscoveryExecutor`, registries, `CompanyPersonService`, `PeopleProviderRegistry`, `BuyerPersona`, oportunidades, eventos, `NextBestActionService` e learning.

## Genericity Test
1. Funciona para Troféus/Eventos?
2. Funciona para Sistemas Web/ERP sem branch especial no core?
3. Engenharia pode entrar por config/provider/signal?

## Opportunity reasoning
Deve explicar: why company, why offer, why now, who decides, how reachable, next best action, evidence/confidence.

Não confundir fit, need, intent, timing, buying power e contactability.

Eventos: `EventSeries → EventOccurrence → organizer → company/lead → opportunity → decision maker → action → outcome → rebuy`.

ERP: technographics são contexto; diferencie software company, user of software, own software, simple vs complex operation.

People: BuyerPersona + role fit + identity confidence + contactability. Nunca invente pessoa.

Learning recomenda; alteração de profile publicado exige aprovação/versionamento enquanto política for human-in-the-loop.
