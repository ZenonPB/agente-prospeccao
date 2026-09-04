# ProspectingProfile como contrato universal de prospecção

> **Status: ✅ FEITO — perfil de prospecção resolvido centralizadamente** (`prospecting_profile_service.resolve_prospecting_profile`): deriva da config do template (sem `if vertical` no core), override explícito por `prescoring_config.profile`, constantes compartilhadas de steps. Entidade versionável com discovery/decision_maker/outreach strategy é evolução (docs 22/25).  
> **Prioridade: P0**  
> **Domínio: Architecture / Vertical Intelligence**

## Problema

O `CampaignScoringTemplate` descreve principalmente critérios de scoring e alguns enrichment steps/playbooks. Para tornar o agente realmente genérico, é necessário descrever também como descobrir, enriquecer, qualificar, achar decisores, interpretar intenção e abordar cada oferta.

## Objetivo

Criar uma entidade/contrato acima do scoring template: `ProspectingProfile`, mantendo o engine agnóstico ao domínio.

## Mudança proposta

O profile deve conter `ideal_customer_profile`, `discovery_strategy`, `enrichment_strategy`, `qualification_model`, `decision_maker_strategy`, `intent_signals`, `exclusion_rules`, `outreach_strategy` e `learning_strategy`. O `CampaignScoringTemplate` pode ser referenciado/migrado como parte do profile.

## Contratos / modelo de dados

```json
{
  "name": "Engenharia Mecânica",
  "ideal_customer_profile": {},
  "discovery_strategy": {},
  "enrichment_strategy": {},
  "qualification_model": {},
  "decision_maker_strategy": {},
  "intent_signals": {},
  "exclusion_rules": {},
  "outreach_strategy": {},
  "learning_strategy": {}
}
```

## Critérios de aceite

- O mesmo engine executa Landing Pages, ERP e Engenharia trocando apenas o profile.
- Nenhum serviço central precisa conter `if vertical == ...` para regras de negócio.
- Profiles são versionáveis e escopáveis por organização.

## Dependências

- CampaignScoringTemplate atual
- TemplateGenerationService atual

## Regra para agentes de IA

Antes de implementar, confirmar os nomes e contratos reais dos arquivos, modelos e serviços no branch atual. Este documento descreve a decisão arquitetural e o comportamento esperado; não deve ser usado para inventar campos ou integrações que ainda não existam. Preservar compatibilidade com o pipeline atual e adicionar testes para qualquer mudança de comportamento.
